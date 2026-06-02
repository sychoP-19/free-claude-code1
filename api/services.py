"""Application services for the Claude-compatible API."""

from __future__ import annotations

import asyncio
import json
import os
import traceback
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from config.settings import Settings
from core.anthropic import get_token_count, get_user_facing_error_message
from core.anthropic.sse import ANTHROPIC_SSE_RESPONSE_HEADERS
from core.cache import ResponseCache, request_cache_key
from providers.base import BaseProvider
from providers.exceptions import InvalidRequestError, ProviderError, RateLimitError

from .dual_brain.intent_classifier import classify_intent, BrainTarget
from .dual_brain.model_override import maybe_override_model
from .detection import (
    is_filepath_extraction_request,
    is_prefix_detection_request,
    is_prompt_rebuild_request,
    is_quota_check_request,
    is_suggestion_mode_request,
    is_title_generation_request,
)
from .model_router import ModelRouter, RoutedMessagesRequest
from .models.anthropic import MessagesRequest, TokenCountRequest
from .models.responses import TokenCountResponse
from .optimization_handlers import try_optimizations
from .prompt_rebuilder import PromptRebuilder
from .web_tools.egress import WebFetchEgressPolicy
from .web_tools.request import (
    is_web_server_tool_request,
    openai_chat_upstream_server_tool_error,
)
from .web_tools.streaming import stream_web_server_tool_response

TokenCounter = Callable[[list[Any], str | list[Any] | None, list[Any] | None], int]

ProviderGetter = Callable[[str], BaseProvider]

# Providers that use ``/chat/completions`` + Anthropic-to-OpenAI conversion (not native Messages).
_OPENAI_CHAT_UPSTREAM_IDS = frozenset({"nvidia_nim", "kimi", "glm"})

# Fail-fast time-to-first-token (seconds): if the primary model emits no first
# chunk within this window, fall over to the configured fallback instead of
# hanging up to the upstream timeout (~300s). Env-overridable; additive only.
_FIRST_TOKEN_TIMEOUT_S = float(os.getenv("FCC_FIRST_TOKEN_TIMEOUT_S", "90"))


def anthropic_sse_streaming_response(
    body: AsyncIterator[str],
) -> StreamingResponse:
    """Return a :class:`StreamingResponse` for Anthropic-style SSE streams."""
    return StreamingResponse(
        body,
        media_type="text/event-stream",
        headers=ANTHROPIC_SSE_RESPONSE_HEADERS,
    )


def _http_status_for_unexpected_service_exception(_exc: BaseException) -> int:
    """HTTP status for uncaught non-provider failures (stable client contract)."""
    return 500


def _log_unexpected_service_exception(
    settings: Settings,
    exc: BaseException,
    *,
    context: str,
    request_id: str | None = None,
) -> None:
    """Log service-layer failures without echoing exception text unless opted in."""
    if settings.log_api_error_tracebacks:
        if request_id is not None:
            logger.error("{} request_id={}: {}", context, request_id, exc)
        else:
            logger.error("{}: {}", context, exc)
        logger.error(traceback.format_exc())
        return
    if request_id is not None:
        logger.error(
            "{} request_id={} exc_type={}",
            context,
            request_id,
            type(exc).__name__,
        )
    else:
        logger.error("{} exc_type={}", context, type(exc).__name__)


def _require_non_empty_messages(messages: list[Any]) -> None:
    if not messages:
        raise InvalidRequestError("messages cannot be empty")


_RESPONSE_CACHE: ResponseCache | None = None


def _get_response_cache(settings: Settings) -> ResponseCache:
    """Lazily build the process-wide response cache."""
    global _RESPONSE_CACHE
    if _RESPONSE_CACHE is None:
        _RESPONSE_CACHE = ResponseCache(
            settings.response_cache_path,
            ttl_seconds=settings.response_cache_ttl_seconds,
        )
    return _RESPONSE_CACHE


async def _replay_cached_sse(sse_text: str) -> AsyncIterator[str]:
    """Replay stored SSE text as a single chunk (byte-identical to the client)."""
    yield sse_text


def _sse_text_is_cacheable(sse_text: str) -> bool:
    """Only cache clean, complete responses (no error / rate-limit events)."""
    if not sse_text:
        return False
    lowered = sse_text.lower()
    return "event: error" not in lowered and "rate_limit_error" not in lowered


class ClaudeProxyService:
    """Coordinate request optimization, model routing, token count, and providers."""

    def __init__(
        self,
        settings: Settings,
        provider_getter: ProviderGetter,
        model_router: ModelRouter | None = None,
        token_counter: TokenCounter = get_token_count,
        prompt_rebuilder: PromptRebuilder | None = None,
    ):
        self._settings = settings
        self._provider_getter = provider_getter
        self._model_router = model_router or ModelRouter(settings)
        self._token_counter = token_counter
        self._prompt_rebuilder = prompt_rebuilder or PromptRebuilder(
            settings, provider_getter
        )

    def _stream_from_resolved(
        self, routed: RoutedMessagesRequest, *, request_id: str | None = None
    ) -> StreamingResponse:
        """Build and return a streaming response for an already-routed request.

        If *request_id* is provided it is reused (useful for correlation when
        the same logical request is retried on a fallback model).
        """
        provider = self._provider_getter(routed.resolved.provider_id)
        provider.preflight_stream(
            routed.request,
            thinking_enabled=routed.resolved.thinking_enabled,
        )

        if request_id is None:
            request_id = f"req_{uuid.uuid4().hex[:12]}"
        logger.info(
            "API_REQUEST: request_id={} model={} messages={}",
            request_id,
            routed.request.model,
            len(routed.request.messages),
        )
        if self._settings.log_raw_api_payloads:
            logger.debug(
                "FULL_PAYLOAD [{}]: {}", request_id, routed.request.model_dump()
            )

        input_tokens = self._token_counter(
            routed.request.messages, routed.request.system, routed.request.tools
        )
        return anthropic_sse_streaming_response(
            provider.stream_response(
                routed.request,
                input_tokens=input_tokens,
                request_id=request_id,
                thinking_enabled=routed.resolved.thinking_enabled,
            ),
        )

    async def _stream_with_fallback(
        self,
        request_data: MessagesRequest,
        routed: RoutedMessagesRequest,
        *,
        request_id: str,
    ) -> StreamingResponse:
        """Stream from the primary model, with automatic fallback on 429/529.

        Because provider ``stream_response`` is an async generator that
        swallows exceptions and emits SSE error events instead, we can't
        catch ``RateLimitError`` outside the generator.  Instead we wrap the
        stream and inspect the first few events: if the very first event is
        an SSE error containing a rate-limit or overloaded semantic, we
        raise immediately so the caller can fall back.
        """
        response = self._stream_from_resolved(routed, request_id=request_id)
        fallback_routed = self._try_fallback_re_resolve(
            request_data, primary_routed=routed
        )
        if fallback_routed is None:
            return response  # No fallback available, serve primary as-is

        # Peek at first event; switch to fallback if the primary rate-limits OR
        # stalls past the first-token timeout (fail fast — still pre-stream, so safe).
        stream_iter = response.body_iterator

        async def _peek_first() -> str:
            return await stream_iter.__anext__()

        try:
            first_chunk = await asyncio.wait_for(
                _peek_first(), timeout=_FIRST_TOKEN_TIMEOUT_S
            )
        except StopAsyncIteration:
            return response  # Empty stream, nothing to do
        except (RateLimitError, TimeoutError):
            logger.info(
                "FALLBACK: primary rate-limited or stalled >{}s, rerouted to {}",
                _FIRST_TOKEN_TIMEOUT_S,
                fallback_routed.resolved.provider_model_ref,
            )
            if hasattr(stream_iter, "aclose"):
                try:
                    await stream_iter.aclose()
                except Exception:  # noqa: BLE001 - best-effort close of stalled stream
                    pass
            return self._stream_from_resolved(fallback_routed, request_id=request_id)

        # If the first SSE chunk signals a rate-limit error, switch
        if isinstance(first_chunk, str) and first_chunk.startswith("data: "):
            try:
                data = json.loads(first_chunk[6:])
                error_type = data.get("error", {}).get("type", "")
                if error_type in ("rate_limit_error", "overloaded_error"):
                    logger.info(
                        "FALLBACK: detected {} in stream, rerouting to {}",
                        error_type,
                        fallback_routed.resolved.provider_model_ref,
                    )
                    return self._stream_from_resolved(
                        fallback_routed, request_id=request_id
                    )
            except (json.JSONDecodeError, AttributeError):
                pass

        # Not a rate-limit error — stitch the first chunk back into the stream and monitor all subsequent chunks
        async def _reattach_first() -> AsyncIterator[str]:
            try:
                yield first_chunk
                async for chunk in stream_iter:
                    # Monitor every chunk for rate limit errors, not just the first one
                    if isinstance(chunk, str) and chunk.startswith("data: "):
                        try:
                            data = json.loads(chunk[6:])
                            error = data.get("error", {})
                            error_type = error.get("type", "")
                            if error_type in ("rate_limit_error", "overloaded_error"):
                                logger.info(
                                    "FALLBACK: detected {} in mid-stream, emitting SSE error",
                                    error_type,
                                )
                                if hasattr(stream_iter, "aclose"):
                                    try:
                                        await stream_iter.aclose()
                                    except Exception:
                                        pass
                                # Emit SSE error event so client can handle gracefully
                                yield f"data: {json.dumps({'error': {'type': error_type, 'message': f'Provider {error_type}; retrying fallback'}})}\n\n"
                                return
                        except (json.JSONDecodeError, AttributeError):
                            pass
                    yield chunk
            finally:
                if hasattr(stream_iter, "aclose"):
                    await stream_iter.aclose()

        return StreamingResponse(
            _reattach_first(),
            media_type="text/event-stream",
            headers=ANTHROPIC_SSE_RESPONSE_HEADERS,
        )

    def _try_fallback_re_resolve(
        self,
        request_data: MessagesRequest,
        *,
        primary_routed: RoutedMessagesRequest | None = None,
    ) -> RoutedMessagesRequest | None:
        """Re-resolve the request using fallback models. Returns None if no fallback."""
        if primary_routed is None:
            primary_routed = self._model_router.resolve_messages_request(request_data)
        fallback_routed = self._model_router.resolve_messages_request(
            request_data, use_fallback=True
        )
        if (
            fallback_routed.resolved.provider_model_ref
            == primary_routed.resolved.provider_model_ref
        ):
            logger.warning(
                "FALLBACK: no distinct fallback configured, primary='{}'",
                primary_routed.resolved.provider_model_ref,
            )
            return None
        logger.warning(
            "RATE_LIMIT_FALLBACK: primary='{}' fallback='{}'",
            primary_routed.resolved.provider_model_ref,
            fallback_routed.resolved.provider_model_ref,
        )
        if fallback_routed.resolved.provider_id in _OPENAI_CHAT_UPSTREAM_IDS:
            tool_err = openai_chat_upstream_server_tool_error(
                fallback_routed.request,
                web_tools_enabled=self._settings.enable_web_server_tools,
            )
            if tool_err is not None:
                logger.warning(
                    "FALLBACK: tool error on fallback provider, skipping: {}", tool_err
                )
                return None
        return fallback_routed

    async def _cached_stream(
        self,
        request_data: MessagesRequest,
        routed: RoutedMessagesRequest,
        request_id: str,
    ) -> StreamingResponse:
        """Serve from the exact-match response cache, else stream and store.

        Only invoked when ``enable_response_cache`` is true, so the normal path
        is byte-for-byte unchanged when the cache is off.
        """
        cache = _get_response_cache(self._settings)
        key = request_cache_key(routed.request)
        cached = cache.get(key)
        if cached is not None:
            logger.info("CACHE_HIT: request_id={} key={}", request_id, key[:12])
            return anthropic_sse_streaming_response(_replay_cached_sse(cached))

        response = await self._stream_with_fallback(
            request_data, routed, request_id=request_id
        )
        source = response.body_iterator

        async def _tee() -> AsyncIterator[str]:
            parts: list[str] = []
            try:
                async for chunk in source:
                    parts.append(chunk)
                    yield chunk
            finally:
                if hasattr(source, "aclose"):
                    await source.aclose()
            sse_text = "".join(parts)
            if _sse_text_is_cacheable(sse_text):
                try:
                    cache.set(key, sse_text)
                    logger.info(
                        "CACHE_STORE: request_id={} key={} bytes={}",
                        request_id,
                        key[:12],
                        len(sse_text),
                    )
                except Exception:  # noqa: BLE001 - cache writes must never break a response
                    logger.debug("CACHE_STORE failed for request_id={}", request_id)

        return anthropic_sse_streaming_response(_tee())

    async def create_message(self, request_data: MessagesRequest) -> object:
        """Create a message response or streaming response."""
        try:
            _require_non_empty_messages(request_data.messages)

            if self._settings.enable_prompt_rebuilding and is_prompt_rebuild_request(
                request_data
            ):
                request_data = await self._prompt_rebuilder.rebuild(request_data)

            routed = self._model_router.resolve_messages_request(request_data)
            if routed.resolved.provider_id in _OPENAI_CHAT_UPSTREAM_IDS:
                tool_err = openai_chat_upstream_server_tool_error(
                    routed.request,
                    web_tools_enabled=self._settings.enable_web_server_tools,
                )
                if tool_err is not None:
                    raise InvalidRequestError(tool_err)

            if self._settings.enable_web_server_tools and is_web_server_tool_request(
                routed.request
            ):
                input_tokens = self._token_counter(
                    routed.request.messages, routed.request.system, routed.request.tools
                )
                logger.info("Optimization: Handling Anthropic web server tool")
                egress = WebFetchEgressPolicy(
                    allow_private_network_targets=self._settings.web_fetch_allow_private_networks,
                    allowed_schemes=self._settings.web_fetch_allowed_scheme_set(),
                )
                return anthropic_sse_streaming_response(
                    stream_web_server_tool_response(
                        routed.request,
                        input_tokens=input_tokens,
                        web_fetch_egress=egress,
                        verbose_client_errors=self._settings.log_api_error_tracebacks,
                    ),
                )

            optimized = try_optimizations(routed.request, self._settings)
            if optimized is not None:
                return optimized
            logger.debug("No optimization matched, routing to provider")

            # Dual-brain routing: classify intent and switch models if configured
            if getattr(self._settings, "dual_brain_enabled", False):
                brain_target = classify_intent(
                    routed.request.messages,
                    system=routed.request.system,
                )
                if brain_target is not BrainTarget.AUTO:
                    override_result = maybe_override_model(
                        routed.request.model,
                        brain_target,
                        self._settings,
                    )
                    if override_result.applied and override_result.overridden_model:
                        logger.info(
                            "DUAL_BRAIN: routed to brain={} model={} (was {})",
                            brain_target.value,
                            override_result.overridden_model,
                            override_result.original_model,
                        )
                        # Update original request model and re-resolve
                        request_data = request_data.model_copy(
                            update={"model": override_result.overridden_model}
                        )
                        routed = self._model_router.resolve_messages_request(
                            request_data
                        )

            request_id = f"req_{uuid.uuid4().hex[:12]}"

            if self._settings.enable_response_cache:
                return await self._cached_stream(request_data, routed, request_id)

            return await self._stream_with_fallback(
                request_data, routed, request_id=request_id
            )

        except ProviderError:
            raise
        except Exception as e:  # Handle unexpected errors with specific logging
            _log_unexpected_service_exception(
                self._settings, e, context="CREATE_MESSAGE_ERROR"
            )
            raise HTTPException(
                status_code=_http_status_for_unexpected_service_exception(e),
                detail=get_user_facing_error_message(e),
            ) from e

    async def create_response(self, request: Request) -> StreamingResponse:
        """Handle OpenAI Responses API requests by converting to/from Anthropic format."""
        from .responses_bridge import (
            AnthropicToResponsesSseAdapter,
            convert_responses_to_anthropic,
        )

        body = await request.json()

        # Convert Responses API request to Anthropic Messages format
        anthr_body = convert_responses_to_anthropic(body)

        # Build a MessagesRequest from the converted body
        messages_request = MessagesRequest(**anthr_body)

        # Delegate to create_message to reuse validation, fallback routing,
        # web tool handling, dual-brain, and optimization pipeline
        response = await self.create_message(messages_request)

        # If create_message returned a StreamingResponse, wrap it with
        # the Responses SSE adapter; otherwise return as-is (e.g. optimization result)
        if isinstance(response, StreamingResponse):
            responses_adapter = AnthropicToResponsesSseAdapter(
                response.body_iterator,
                model=body.get("model", messages_request.model),
                request_id=None,
            )
            return StreamingResponse(
                responses_adapter.adapt(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        return response

    def count_tokens(self, request_data: TokenCountRequest) -> TokenCountResponse:
        """Count tokens for a request after applying configured model routing."""
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        with logger.contextualize(request_id=request_id):
            try:
                _require_non_empty_messages(request_data.messages)
                routed = self._model_router.resolve_token_count_request(request_data)
                tokens = self._token_counter(
                    routed.request.messages, routed.request.system, routed.request.tools
                )
                logger.info(
                    "COUNT_TOKENS: request_id={} model={} messages={} input_tokens={}",
                    request_id,
                    routed.request.model,
                    len(routed.request.messages),
                    tokens,
                )
                return TokenCountResponse(input_tokens=tokens)
            except ProviderError:
                raise
            except Exception as e:
                _log_unexpected_service_exception(
                    self._settings,
                    e,
                    context="COUNT_TOKENS_ERROR",
                    request_id=request_id,
                )
                raise HTTPException(
                    status_code=_http_status_for_unexpected_service_exception(e),
                    detail=get_user_facing_error_message(e),
                ) from e
