"""Registry — checks which ai-repositories are present on disk and their service status."""
from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

_ROOT = Path(__file__).parent.parent.parent / "ai-repositories"

# (name, default_port_or_None, description)
_REPO_META: list[tuple[str, int | None, str]] = [
    ("AI-Youtube-Shorts-Generator", None,  "Shorts pipeline (clip extraction)"),
    ("Pixelle-Video",               8080,  "Full video generation (ComfyUI-backed)"),
    ("ComfyUI",                     8188,  "Stable Diffusion / image gen UI"),
    ("stable-diffusion-webui",      7860,  "SD AUTOMATIC1111 web UI"),
    ("GPT-SoVITS",                  9880,  "Neural voice cloning (TTS)"),
    ("F5-TTS",                      None,  "F5-TTS zero-shot voice synthesis"),
    ("chatterbox",                  None,  "Chatterbox multilingual TTS"),
    ("kokoro",                      None,  "Kokoro high-quality TTS"),
    ("faster-whisper",              None,  "Fast Whisper transcription"),
    ("ShortGPT",                    None,  "AI short video automation"),
    ("TTS",                         None,  "Coqui TTS voice synthesis"),
    ("n8n-mcp",                     5678,  "n8n workflow automation"),
    ("yt-dlp",                      None,  "Video downloader"),
    ("text-audio",                  None,  "Text-to-audio pipeline"),
    ("ruflo",                       None,  "Video tools"),
    ("TradingAgents",               None,  "Trading AI agents"),
    ("open-webui",                  3000,  "Open WebUI for Ollama"),
    ("dify",                        None,  "Dify LLMOps platform"),
    ("AgentGPT",                    None,  "Autonomous AI agents"),
    ("moviepy",                     None,  "Python video editing library"),
]

_REPO_NAMES = [m[0] for m in _REPO_META]

REPOS = [
    {"name": m[0], "path": str(_ROOT / m[0]), "ok": (_ROOT / m[0]).exists(),
     "port": m[1], "description": m[2]}
    for m in _REPO_META
]


def check_all() -> list[dict]:
    return [
        {"name": m[0], "path": str(_ROOT / m[0]), "ok": (_ROOT / m[0]).exists(),
         "port": m[1], "description": m[2]}
        for m in _REPO_META
    ]


def ok_count(repos: list[dict]) -> int:
    return sum(1 for r in repos if r["ok"])


async def check_services() -> list[dict]:
    """Ping each repo's service port (if any) to determine live status."""
    repos = check_all()
    serviced = [r for r in repos if r["port"]]

    async def _ping(repo: dict) -> dict:
        port = repo["port"]
        url = f"http://localhost:{port}"
        try:
            async with httpx.AsyncClient(timeout=2) as c:
                r = await c.get(url)
                repo["running"] = r.status_code < 500
        except Exception:
            repo["running"] = False
        return repo

    pinged = await asyncio.gather(*[_ping(r) for r in serviced], return_exceptions=True)
    running_map = {}
    for result in pinged:
        if isinstance(result, dict):
            running_map[result["name"]] = result.get("running", False)

    for repo in repos:
        if repo["name"] in running_map:
            repo["running"] = running_map[repo["name"]]
        elif repo["port"] is None:
            repo["running"] = None  # no HTTP service
        else:
            repo["running"] = False

    return repos
