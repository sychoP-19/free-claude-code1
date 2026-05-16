"""LLM client — Ollama local LLM integration.

Supports: Ollama API (local), with fallback to OpenAI-compatible endpoints.
"""

from __future__ import annotations

import json
import httpx


class LocalLLMClient:
    def __init__(self, config: dict):
        self.provider = config["llm"]["provider"]
        self.model = config["llm"]["model"]
        self.base_url = config["llm"]["base_url"]
        self.temperature = config["llm"]["temperature"]
        self.max_tokens = config["llm"]["max_tokens"]

    def chat(self, system: str, user: str) -> str:
        if self.provider == "ollama":
            return self._ollama_chat(system, user)
        return self._openai_compat_chat(system, user)

    def _ollama_chat(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
        }
        resp = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=120.0)
        resp.raise_for_status()
        return resp.json()["message"]["content"]

    def _openai_compat_chat(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        url = f"{self.base_url}/v1/chat/completions"
        resp = httpx.post(url, json=payload, timeout=120.0)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
