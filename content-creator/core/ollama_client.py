import httpx
import json
from typing import AsyncIterator


OLLAMA_BASE = "http://localhost:11434"


async def generate(model: str, prompt: str, system: str = "") -> str:
    payload = {"model": model, "prompt": prompt, "stream": False}
    if system:
        payload["system"] = system
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{OLLAMA_BASE}/api/generate", json=payload)
        resp.raise_for_status()
        return resp.json().get("response", "")


async def chat(model: str, messages: list, system: str = "") -> str:
    payload = {"model": model, "messages": messages, "stream": False}
    if system:
        payload["system"] = system
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")


async def list_models() -> list:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            resp.raise_for_status()
            return resp.json().get("models", [])
    except Exception:
        return []


async def pull_model(model: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=600) as client:
            async with client.stream("POST", f"{OLLAMA_BASE}/api/pull", json={"name": model}) as resp:
                async for line in resp.aiter_lines():
                    if line:
                        data = json.loads(line)
                        if data.get("status") == "success":
                            return True
        return True
    except Exception:
        return False


async def is_available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


def pick_model(models: list, preferred: list) -> str:
    names = {m.get("name", "").split(":")[0] for m in models}
    for p in preferred:
        base = p.split(":")[0]
        if base in names:
            return p
    return preferred[0] if preferred else "mistral:7b"
