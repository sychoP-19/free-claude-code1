"""
Universal LLM client for MAJD Empire OS.
Fallback chain: free proxy (localhost:8082) → Ollama → offline template.
"""
import json
import logging
import os
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_FREE_PROXY = os.environ.get("LLM_PROXY_URL", "http://localhost:8082")
_OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
_DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:latest")
_TIMEOUT = 90


async def llm_complete(
    prompt: str,
    system: str = "You are a helpful AI assistant. Return only what is asked.",
    model: str | None = None,
    json_mode: bool = False,
) -> str:
    """
    Complete a prompt using the best available LLM.
    Tries: free proxy → Ollama → returns empty string (caller must handle fallback).
    """
    result = await _try_proxy(prompt, system)
    if result:
        return _extract_json(result) if json_mode else result

    result = await _try_ollama(prompt, system, model or _DEFAULT_MODEL)
    if result:
        return _extract_json(result) if json_mode else result

    logger.warning("All LLM backends unavailable — returning empty")
    return ""


async def llm_json(prompt: str, system: str = "Return ONLY valid JSON, no explanation.") -> dict | None:
    """Complete a prompt and parse the response as JSON. Returns None on failure."""
    raw = await llm_complete(prompt, system=system, json_mode=True)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


async def _try_proxy(prompt: str, system: str) -> str:
    """Try the free proxy (Claude via NVIDIA NIM / OpenRouter)."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            payload: dict[str, Any] = {
                "model": "claude-sonnet-4-6",
                "max_tokens": 2048,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                payload["system"] = system
            resp = await client.post(f"{_FREE_PROXY}/v1/messages", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("content", [])
                if content and isinstance(content, list):
                    return content[0].get("text", "")
                return data.get("content", "")
    except Exception as exc:
        logger.debug("Proxy unavailable: %s", exc)
    return ""


async def _try_ollama(prompt: str, system: str, model: str) -> str:
    """Try local Ollama."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            # First verify Ollama is up
            health = await client.get(f"{_OLLAMA_BASE}/api/tags", timeout=5)
            if health.status_code != 200:
                return ""
            # Pick first available model if requested model not found
            available = [m.get("name", "") for m in health.json().get("models", [])]
            use_model = model if any(model.split(":")[0] in m for m in available) else (available[0] if available else model)

            payload = {"model": use_model, "prompt": prompt, "stream": False}
            if system:
                payload["system"] = system
            resp = await client.post(f"{_OLLAMA_BASE}/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "")
    except Exception as exc:
        logger.debug("Ollama unavailable: %s", exc)
    return ""


def _extract_json(text: str) -> str:
    """Extract JSON object from text if present."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group() if match else text


async def is_proxy_alive() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{_FREE_PROXY}/health")
            return r.status_code < 400
    except Exception:
        return False


async def is_ollama_alive() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{_OLLAMA_BASE}/api/tags")
            return r.status_code == 200
    except Exception:
        return False
