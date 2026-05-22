"""pipelines/llm.py — unified LLM client.

Tries the local free-claude-code proxy at :8082 first (Anthropic messages
format, SSE streaming) and falls back to Ollama at :11434 on any failure.
Every call is logged to the SQLite costs table so the tracker page shows
real numbers.

NOTE: The free-claude-code proxy ALWAYS returns SSE (text/event-stream)
regardless of the `stream` flag. _try_proxy therefore reads the SSE stream
and accumulates text_delta events instead of calling r.json().
"""
from __future__ import annotations

import json
import os
import time

import httpx

from core import db

PROXY_URL  = os.environ.get("JARVIS_PROXY_URL", "http://localhost:8082/v1/messages")
OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_PROXY_MODEL  = os.environ.get("JARVIS_PROXY_MODEL",  "nvidia_nim/meta/llama-3.3-70b-instruct")
DEFAULT_OLLAMA_MODEL = os.environ.get("JARVIS_OLLAMA_MODEL", "llama3.1:8b")
# Auth for the local free-claude-code proxy. Falls back to "freecc" which is
# the default token shipped with the proxy's example .env.
PROXY_API_KEY = (
    os.environ.get("ANTHROPIC_AUTH_TOKEN")
    or os.environ.get("JARVIS_PROXY_KEY")
    or "freecc"
)


class LLMError(RuntimeError):
    """Raised when both proxy and Ollama fail."""


async def chat(messages: list[dict],
               system: str = "",
               max_tokens: int = 1024,
               run_id: int | None = None,
               temperature: float = 0.7) -> str:
    """Send a chat completion. Returns the assistant text or raises LLMError."""
    proxy_err = await _try_proxy(messages, system, max_tokens, run_id, temperature)
    if isinstance(proxy_err, str):
        return proxy_err
    ollama_err = await _try_ollama(messages, system, max_tokens, run_id, temperature)
    if isinstance(ollama_err, str):
        return ollama_err
    raise LLMError(f"proxy: {proxy_err} | ollama: {ollama_err}")


def _parse_sse_text(raw: str) -> tuple[str, int, int]:
    """Parse SSE response body, return (text, input_tokens, output_tokens)."""
    text_parts: list[str] = []
    input_tokens = 0
    output_tokens = 0
    for line in raw.splitlines():
        if not line.startswith("data: "):
            continue
        data = line[6:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            ev = json.loads(data)
        except json.JSONDecodeError:
            continue
        # text_delta events carry the text fragment
        ev_type = ev.get("type", "")
        if ev_type == "content_block_delta":
            delta = ev.get("delta", {})
            text_parts.append(delta.get("text", ""))
        elif ev_type == "message_start":
            usage = ev.get("message", {}).get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
        elif ev_type == "message_delta":
            usage = ev.get("usage", {})
            output_tokens = usage.get("output_tokens", 0)
    return "".join(text_parts).strip(), input_tokens, output_tokens


async def _try_proxy(messages, system, max_tokens, run_id, temperature):
    started = time.time()
    payload = {
        "model":       DEFAULT_PROXY_MODEL,
        "max_tokens":  max_tokens,
        "messages":    messages,
        "stream":      True,   # proxy always streams; request it explicitly
        "temperature": temperature,
    }
    if system:
        payload["system"] = system
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(
                PROXY_URL,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": PROXY_API_KEY,
                    "anthropic-version": "2023-06-01",
                },
            )
            r.raise_for_status()
            raw = r.text

        text, tokens_in, tokens_out = _parse_sse_text(raw)
        if not text:
            raise RuntimeError("empty response from proxy SSE stream")
        if "Provider API request failed" in text or "API request failed" in text:
            raise RuntimeError(f"proxy backend error: {text[:120]}")

        latency = int((time.time() - started) * 1000)
        db.log_cost(
            route="proxy",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency, ok=True, run_id=run_id, note=DEFAULT_PROXY_MODEL,
        )
        return text
    except Exception as e:
        latency = int((time.time() - started) * 1000)
        db.log_cost(route="proxy", latency_ms=latency, ok=False, run_id=run_id,
                    note=f"{type(e).__name__}: {e}")
        return e


async def _try_ollama(messages, system, max_tokens, run_id, temperature):
    started = time.time()
    msgs = list(messages)
    if system:
        msgs = [{"role": "system", "content": system}] + msgs
    payload = {
        "model": DEFAULT_OLLAMA_MODEL,
        "stream": False,
        "messages": msgs,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    try:
        async with httpx.AsyncClient(timeout=180) as c:
            r = await c.post(f"{OLLAMA_URL}/api/chat", json=payload)
            r.raise_for_status()
            j = r.json()
        text = ((j.get("message") or {}).get("content") or "").strip()
        if not text:
            raise RuntimeError("empty ollama response")
        latency = int((time.time() - started) * 1000)
        db.log_cost(
            route="ollama",
            tokens_in=j.get("prompt_eval_count", 0),
            tokens_out=j.get("eval_count", 0),
            latency_ms=latency, ok=True, run_id=run_id, note=DEFAULT_OLLAMA_MODEL,
        )
        return text
    except Exception as e:
        latency = int((time.time() - started) * 1000)
        db.log_cost(route="ollama", latency_ms=latency, ok=False, run_id=run_id,
                    note=f"{type(e).__name__}: {e}")
        return e


async def health() -> dict:
    """Quick ping of both backends. Used by /api/system/llm-health."""
    proxy_ok = False
    ollama_ok = False
    started = time.time()
    async with httpx.AsyncClient(timeout=5) as c:
        try:
            base = PROXY_URL.rsplit("/v1/", 1)[0] + "/v1/models"
            r = await c.get(base, headers={"x-api-key": PROXY_API_KEY})
            proxy_ok = r.status_code < 500
        except Exception:
            proxy_ok = False
        try:
            r = await c.get(f"{OLLAMA_URL}/api/tags")
            ollama_ok = r.status_code == 200
        except Exception:
            ollama_ok = False
    return {
        "proxy":      proxy_ok,
        "ollama":     ollama_ok,
        "latency_ms": int((time.time() - started) * 1000),
        "proxy_url":  PROXY_URL,
        "ollama_url": OLLAMA_URL,
    }
