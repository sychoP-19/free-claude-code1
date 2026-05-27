"""Bridge between OpenAI Responses API and Anthropic Messages API formats.

Converts request bodies from OpenAI Responses API format to Anthropic Messages
format, and adapts Anthropic SSE streams into OpenAI Responses SSE events.
This lets Codex CLI (which speaks the Responses API at ``/v1/responses``) talk
through the existing proxy to NVIDIA NIM providers.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from loguru import logger


# ---------------------------------------------------------------------------
# Request conversion: OpenAI Responses API -> Anthropic Messages API
# ---------------------------------------------------------------------------


def _convert_content_part(part: dict[str, Any] | str) -> list[dict[str, Any]]:
    """Convert a single Responses API content part to Anthropic content blocks."""
    if isinstance(part, str):
        return [{"type": "text", "text": part}]

    ptype = part.get("type", "")

    if ptype == "input_text":
        return [{"type": "text", "text": part.get("text", "")}]

    if ptype == "input_image":
        image_url = part.get("image_url", "")
        return [{"type": "image", "source": {"type": "url", "url": image_url}}]

    # Fallback: wrap unknown types as text if they have a text field
    if "text" in part:
        return [{"type": "text", "text": part["text"]}]

    logger.warning("responses_bridge: skipping unknown content part type={}", ptype)
    return []


def _convert_content(content: dict[str, Any] | str | list[Any]) -> list[dict[str, Any]]:
    """Convert a Responses API content field to Anthropic content blocks."""
    if isinstance(content, str):
        return [{"type": "text", "text": content}]

    if isinstance(content, list):
        blocks: list[dict[str, Any]] = []
        for part in content:
            blocks.extend(_convert_content_part(part))
        return blocks

    # Single dict part
    return _convert_content_part(content)


def _convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Responses API function tools to Anthropic tool format."""
    anthropic_tools: list[dict[str, Any]] = []
    for tool in tools:
        ttype = tool.get("type", "")
        if ttype == "function":
            func = tool.get("function", {})
            anthropic_tools.append({
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {}),
            })
        else:
            # Pass through non-function tools (e.g. web_search) as-is
            anthropic_tools.append(tool)
    return anthropic_tools


def _safe_parse_json(text: str) -> dict[str, Any]:
    """Parse JSON string, returning empty dict on failure."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}


def convert_responses_to_anthropic(request: dict[str, Any]) -> dict[str, Any]:
    """Convert an OpenAI Responses API request body to Anthropic Messages API body.

    Handles:
    - System instructions extraction (``instructions`` field or system-role items)
    - Role-based message mapping with content type conversion
    - ``function_call`` input items -> Anthropic assistant ``tool_use`` blocks
    - ``function_call_output`` input items -> Anthropic user ``tool_result`` blocks
    - Consecutive same-role message merging (Anthropic requires alternating roles)
    - String input shorthand (single user message)
    - Content part conversion (input_text, input_image)
    - Tool definition conversion
    """
    result: dict[str, Any] = {}

    # Model passthrough
    result["model"] = request.get("model", "")

    # --- System prompt assembly ---
    system_parts: list[str] = []

    # Top-level "instructions"
    instructions = request.get("instructions")
    if isinstance(instructions, str) and instructions:
        system_parts.append(instructions)
    elif isinstance(instructions, list):
        for part in instructions:
            if isinstance(part, str):
                system_parts.append(part)
            elif isinstance(part, dict) and part.get("type") == "input_text":
                system_parts.append(part.get("text", ""))

    # --- Input items ---
    raw_input = request.get("input", [])

    # String input shorthand: treat as single user message
    if isinstance(raw_input, str):
        raw_input = [{"role": "user", "content": raw_input}]

    # Separate system-role items from conversation items
    input_items: list[dict[str, Any]] = []
    for item in raw_input:
        if not isinstance(item, dict):
            continue
        if item.get("role") == "system":
            content = item.get("content", "")
            if isinstance(content, str) and content:
                system_parts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "input_text":
                        system_parts.append(part.get("text", ""))
                    elif isinstance(part, str):
                        system_parts.append(part)
        else:
            input_items.append(item)

    if system_parts:
        result["system"] = "\n\n".join(system_parts)

    # --- Build Anthropic messages with role merging ---
    messages: list[dict[str, Any]] = []

    for item in input_items:
        item_type = item.get("type", "")
        role = item.get("role", "")

        if item_type == "function_call":
            _append_function_call(messages, item)
            continue

        if item_type == "function_call_output":
            _append_function_call_output(messages, item)
            continue

        if role in ("user", "assistant"):
            content = item.get("content")
            if content is None:
                continue
            anthropic_content = _convert_content(content)
            _merge_message(messages, role, anthropic_content)
            continue

        logger.warning(
            "responses_bridge: skipping unknown input item type={} role={}",
            item_type,
            role,
        )

    result["messages"] = messages

    # --- Tools ---
    tools = request.get("tools")
    if tools:
        result["tools"] = _convert_tools(tools)

    # --- Scalar fields ---
    if "temperature" in request:
        result["temperature"] = request["temperature"]
    if "max_output_tokens" in request:
        result["max_tokens"] = request["max_output_tokens"]
    if "top_p" in request:
        result["top_p"] = request["top_p"]
    if "stop_sequences" in request:
        result["stop_sequences"] = request["stop_sequences"]

    # Proxy always streams
    result["stream"] = True

    return result


def _merge_message(
    messages: list[dict[str, Any]],
    role: str,
    content_blocks: list[dict[str, Any]],
) -> None:
    """Append content_blocks to the last message if same role, else create new."""
    if messages and messages[-1]["role"] == role:
        existing = messages[-1]["content"]
        if not isinstance(existing, list):
            existing = [{"type": "text", "text": existing}]
            messages[-1]["content"] = existing
        existing.extend(content_blocks)
    else:
        messages.append({"role": role, "content": content_blocks})


def _append_function_call(
    messages: list[dict[str, Any]], item: dict[str, Any]
) -> None:
    """Append a function_call input item as an assistant tool_use block."""
    call_id = item.get("call_id", item.get("id", f"toolu_{uuid.uuid4().hex[:12]}"))
    name = item.get("name", "")
    arguments_str = item.get("arguments", "{}")
    arguments_parsed = (
        _safe_parse_json(arguments_str) if isinstance(arguments_str, str) else arguments_str
    )

    tool_use_block: dict[str, Any] = {
        "type": "tool_use",
        "id": call_id,
        "name": name,
        "input": arguments_parsed,
    }

    # Append to previous assistant message or create new one
    if messages and messages[-1]["role"] == "assistant":
        existing = messages[-1]["content"]
        if not isinstance(existing, list):
            existing = [{"type": "text", "text": existing}]
            messages[-1]["content"] = existing
        existing.append(tool_use_block)
    else:
        messages.append({"role": "assistant", "content": [tool_use_block]})


def _append_function_call_output(
    messages: list[dict[str, Any]], item: dict[str, Any]
) -> None:
    """Append a function_call_output input item as a user tool_result block."""
    call_id = item.get("call_id", "")
    output = item.get("output", "")

    tool_result_block: dict[str, Any] = {
        "type": "tool_result",
        "tool_use_id": call_id,
        "content": output,
    }

    # Append to previous user message or create new one
    if messages and messages[-1]["role"] == "user":
        existing = messages[-1]["content"]
        if not isinstance(existing, list):
            existing = [{"type": "text", "text": existing}]
            messages[-1]["content"] = existing
        existing.append(tool_result_block)
    else:
        messages.append({"role": "user", "content": [tool_result_block]})


# ---------------------------------------------------------------------------
# SSE adaptation: Anthropic Messages stream -> OpenAI Responses stream
# ---------------------------------------------------------------------------


def _sse(event: str, data: dict[str, Any]) -> str:
    """Format a single SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class AnthropicToResponsesSseAdapter:
    """Wrap an Anthropic SSE stream and yield OpenAI Responses API SSE events.

    Tracks block state (current type, accumulated text, tool info) across the
    Anthropic event sequence and emits the corresponding Responses events.
    """

    def __init__(
        self,
        anthropic_sse_stream: AsyncIterator[str],
        model: str,
        request_id: str,
    ) -> None:
        self._stream = anthropic_sse_stream
        self._model = model
        self._request_id = request_id
        self._resp_id = f"resp_{uuid.uuid4().hex[:16]}"
        self._created_at = int(time.time())

        # Block state
        self._output_index: int = -1
        self._content_index: int = -1
        self._current_block_type: str | None = None
        self._accumulated_text: list[str] = []
        self._accumulated_tool_args: list[str] = []
        self._current_tool_id: str = ""
        self._current_tool_name: str = ""

        # Usage tracking
        self._input_tokens: int = 0
        self._output_tokens: int = 0

        # Completed output items for response.completed
        self._output_items: list[dict[str, Any]] = []

        # Current open message item content
        self._current_message_content: list[dict[str, Any]] = []
        self._message_item_open: bool = False

    # -- Event emitters --

    def _emit_created(self) -> str:
        return _sse("response.created", {
            "id": self._resp_id,
            "object": "response",
            "status": "in_progress",
            "model": self._model,
            "output": [],
            "created_at": self._created_at,
        })

    def _ensure_message_item(self) -> str:
        """Open a message output item if one is not already open."""
        if self._message_item_open:
            return ""
        self._output_index += 1
        self._content_index = -1
        self._current_message_content = []
        self._message_item_open = True
        return _sse("response.output_item.added", {
            "output_index": self._output_index,
            "item": {"type": "message", "role": "assistant", "content": []},
        })

    def _close_message_item(self) -> str:
        """Close the current open message item, if any."""
        if not self._message_item_open:
            return ""
        self._message_item_open = False
        content = self._current_message_content
        item: dict[str, Any] = {"type": "message", "role": "assistant", "content": content}
        self._output_items.append(item)
        return _sse("response.output_item.done", {
            "output_index": self._output_index,
            "item": item,
        })

    def _emit_text_part_added(self) -> str:
        self._content_index += 1
        self._accumulated_text = []
        return _sse("response.content_part.added", {
            "output_index": self._output_index,
            "content_index": self._content_index,
            "part": {"type": "output_text", "text": ""},
        })

    def _emit_text_delta(self, text: str) -> str:
        return _sse("response.output_text.delta", {
            "output_index": self._output_index,
            "content_index": self._content_index,
            "delta": text,
        })

    def _emit_text_done(self) -> str:
        full_text = "".join(self._accumulated_text)
        part: dict[str, Any] = {"type": "output_text", "text": full_text}
        self._current_message_content.append(part)
        return (
            _sse("response.output_text.done", {
                "output_index": self._output_index,
                "content_index": self._content_index,
                "text": full_text,
            })
            + _sse("response.content_part.done", {
                "output_index": self._output_index,
                "content_index": self._content_index,
                "part": part,
            })
        )

    def _emit_function_call_item_added(self) -> str:
        """Start a function_call output item (closes any open message item first)."""
        events = self._close_message_item()
        self._output_index += 1
        self._content_index = -1
        self._accumulated_tool_args = []
        fc_id = f"fc_{uuid.uuid4().hex[:12]}"
        return events + _sse("response.output_item.added", {
            "output_index": self._output_index,
            "item": {
                "type": "function_call",
                "id": fc_id,
                "call_id": self._current_tool_id,
                "name": self._current_tool_name,
                "arguments": "",
            },
        })

    def _emit_function_call_args_delta(self, delta: str) -> str:
        return _sse("response.function_call_arguments.delta", {
            "output_index": self._output_index,
            "delta": delta,
        })

    def _emit_function_call_done(self) -> str:
        full_args = "".join(self._accumulated_tool_args)
        item: dict[str, Any] = {
            "type": "function_call",
            "id": f"fc_{uuid.uuid4().hex[:12]}",
            "call_id": self._current_tool_id,
            "name": self._current_tool_name,
            "arguments": full_args,
        }
        self._output_items.append(item)
        return (
            _sse("response.function_call_arguments.done", {
                "output_index": self._output_index,
                "arguments": full_args,
            })
            + _sse("response.output_item.done", {
                "output_index": self._output_index,
                "item": item,
            })
        )

    def _emit_completed(self) -> str:
        return _sse("response.completed", {
            "id": self._resp_id,
            "object": "response",
            "status": "completed",
            "model": self._model,
            "output": self._output_items,
            "usage": {
                "input_tokens": self._input_tokens,
                "output_tokens": self._output_tokens,
            },
        })

    # -- Anthropic event handlers --

    def _handle_message_start(self, data: dict[str, Any]) -> str:
        msg = data.get("message", {})
        usage = msg.get("usage", {})
        self._input_tokens = usage.get("input_tokens", 0)
        return self._emit_created()

    def _handle_content_block_start(self, data: dict[str, Any]) -> str:
        block = data.get("content_block", {})
        block_type = block.get("type", "text")
        self._current_block_type = block_type

        if block_type == "text":
            return self._ensure_message_item() + self._emit_text_part_added()

        if block_type == "tool_use":
            self._current_tool_id = block.get("id", "")
            self._current_tool_name = block.get("name", "")
            return self._emit_function_call_item_added()

        if block_type == "thinking":
            # Thinking blocks are not exposed in Responses API
            logger.debug("responses_bridge: skipping thinking block in SSE adaptation")
            return ""

        return ""

    def _handle_content_block_delta(self, data: dict[str, Any]) -> str:
        delta = data.get("delta", {})
        delta_type = delta.get("type", "")

        if self._current_block_type == "text" and delta_type == "text_delta":
            text = delta.get("text", "")
            self._accumulated_text.append(text)
            return self._emit_text_delta(text)

        if self._current_block_type == "tool_use" and delta_type == "input_json_delta":
            partial = delta.get("partial_json", "")
            self._accumulated_tool_args.append(partial)
            return self._emit_function_call_args_delta(partial)

        # Silently skip unknown delta types (e.g. thinking_delta)
        return ""

    def _handle_content_block_stop(self) -> str:
        if self._current_block_type == "text":
            result = self._emit_text_done()
        elif self._current_block_type == "tool_use":
            result = self._emit_function_call_done()
        else:
            result = ""

        self._current_block_type = None
        return result

    def _handle_message_delta(self, data: dict[str, Any]) -> str:
        usage = data.get("usage", {})
        self._output_tokens = usage.get("output_tokens", self._output_tokens)
        return ""

    def _handle_message_stop(self) -> str:
        return self._close_message_item() + self._emit_completed()

    # -- SSE parsing --

    def _parse_sse_line(self, line: str) -> tuple[str, dict[str, Any]] | None:
        """Parse a data: line into (event_type, parsed_body) or None."""
        if not line.startswith("data: "):
            return None
        raw = line[len("data: "):]
        if not raw or raw == "[DONE]":
            return None
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
        event_type = parsed.get("type", "")
        return (event_type, parsed) if event_type else None

    # -- Main iteration --

    async def adapt(self) -> AsyncIterator[str]:
        """Yield Responses-format SSE ``event: ...\\ndata: ...\\n\\n`` strings."""
        current_event_type: str | None = None

        try:
            async for line in self._stream:
                line = line.rstrip("\n").rstrip("\r")

                if line.startswith("event: "):
                    current_event_type = line[len("event: "):]
                    continue

                if not line.startswith("data: "):
                    if not line:
                        current_event_type = None
                    continue

                parsed = self._parse_sse_line(line)
                if parsed is None:
                    continue

                event_type, data = parsed
                # Prefer explicit event: line when present
                if current_event_type and current_event_type != event_type:
                    event_type = current_event_type
                current_event_type = None

                out = ""

                if event_type == "message_start":
                    out = self._handle_message_start(data)
                elif event_type == "content_block_start":
                    out = self._handle_content_block_start(data)
                elif event_type == "content_block_delta":
                    out = self._handle_content_block_delta(data)
                elif event_type == "content_block_stop":
                    out = self._handle_content_block_stop()
                elif event_type == "message_delta":
                    out = self._handle_message_delta(data)
                elif event_type == "message_stop":
                    out = self._handle_message_stop()
                elif event_type == "ping":
                    pass
                elif event_type == "error":
                    err_data = data.get("error", data)
                    out = _sse("response.error", {
                        "id": self._resp_id,
                        "object": "response",
                        "status": "failed",
                        "model": self._model,
                        "error": err_data,
                    })
                else:
                    logger.debug(
                        "responses_bridge: unhandled Anthropic SSE event type={}",
                        event_type,
                    )

                if out:
                    yield out

        except Exception as exc:
            logger.error("responses_bridge: stream error: {}", exc)
            yield _sse("response.error", {
                "id": self._resp_id,
                "object": "response",
                "status": "failed",
                "model": self._model,
                "error": {"type": "stream_error", "message": str(exc)},
            })
