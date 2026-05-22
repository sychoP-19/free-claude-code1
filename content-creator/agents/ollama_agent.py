"""Ollama local LLM agent."""
import asyncio
import json
import logging
import os
from typing import AsyncIterator, Optional

import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

JARVIS_SYSTEM = """You are JARVIS — an AI assistant integrated into a content intelligence dashboard. You help creators grow YouTube channels, generate viral content, analyze trends, and build monetization systems. You have access to agents that can: analyze channels, mine trends, generate scripts, detect highlights in videos, create shorts, generate images with FAL.ai, download and transcribe any video, and track revenue. Be concise, tactical, and always suggest actionable next steps."""


async def list_models() -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            r.raise_for_status()
            return r.json().get("models", [])
    except Exception as e:
        logger.debug("Ollama unavailable: %s", e)
        return []


async def chat(
    message: str,
    model: str = "llama3.1:8b",
    history: Optional[list] = None,
    system: Optional[str] = None,
) -> dict:
    messages = [{"role": "system", "content": system or JARVIS_SYSTEM}]
    if history:
        messages.extend(history[-20:])
    messages.append({"role": "user", "content": message})

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": model, "messages": messages, "stream": False},
        )
        r.raise_for_status()
        data = r.json()
        reply = data.get("message", {}).get("content", "")
        return {
            "reply":   reply,
            "model":   model,
            "tokens":  data.get("eval_count", 0),
            "history": messages + [{"role": "assistant", "content": reply}],
        }


async def stream_chat(
    message: str,
    model: str = "llama3.1:8b",
    history: Optional[list] = None,
    system: Optional[str] = None,
) -> AsyncIterator[str]:
    messages = [{"role": "system", "content": system or JARVIS_SYSTEM}]
    if history:
        messages.extend(history[-20:])
    messages.append({"role": "user", "content": message})

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_URL}/api/chat",
            json={"model": model, "messages": messages, "stream": True},
        ) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if chunk.get("done"):
                        break
                except json.JSONDecodeError:
                    continue


async def analyze_content(text: str, task: str = "virality", model: str = "llama3.1:latest") -> dict:
    prompts = {
        "virality": f"Rate the viral potential of this content from 1-10 and explain why in 3 bullet points:\n\n{text}",
        "hooks":    f"Extract the 5 strongest hook moments from this transcript. For each: timestamp hint, hook text, why it works:\n\n{text}",
        "script":   f"Transform this transcript into a punchy 60-second YouTube Short script with a viral hook:\n\n{text}",
        "seo":      f"Generate 10 SEO-optimized YouTube title ideas and 5 description keywords for:\n\n{text}",
    }
    prompt = prompts.get(task, prompts["virality"])
    return await chat(prompt, model=model)
