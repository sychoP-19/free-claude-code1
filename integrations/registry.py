from pathlib import Path

AI_REPOS_DIR = Path(__file__).parent.parent / "ai-repositories"

REPOS = {
    "stable-diffusion-webui": {
        "url": "https://github.com/AUTOMATIC1111/stable-diffusion-webui",
        "description": "Stable Diffusion Web UI",
    },
    "ComfyUI": {
        "url": "https://github.com/comfyanonymous/ComfyUI",
        "description": "Node-based Stable Diffusion UI",
    },
    "whisper": {
        "url": "https://github.com/openai/whisper",
        "description": "Speech-to-text transcription",
    },
    "yt-dlp": {
        "url": "https://github.com/yt-dlp/yt-dlp",
        "description": "Video downloader",
    },
    "ffmpeg-python": {
        "url": "https://github.com/kkroening/ffmpeg-python",
        "description": "ffmpeg Python bindings",
    },
    "moviepy": {
        "url": "https://github.com/Zulko/moviepy",
        "description": "Video editing library",
    },
    "ollama-python": {
        "url": "https://github.com/ollama/ollama-python",
        "description": "Ollama Python SDK",
    },
    "TTS": {
        "url": "https://github.com/coqui-ai/TTS",
        "description": "Text-to-speech engine",
    },
    "open-interpreter": {
        "url": "https://github.com/OpenInterpreter/open-interpreter",
        "description": "Code interpreter agent",
    },
    "AgentGPT": {
        "url": "https://github.com/reworkd/AgentGPT",
        "description": "Autonomous agent framework",
    },
}


def check_all() -> dict[str, dict]:
    results = {}
    for name, info in REPOS.items():
        repo_path = AI_REPOS_DIR / name
        exists = repo_path.exists() and repo_path.is_dir()
        size = _dir_size(repo_path) if exists else None
        results[name] = {
            "status":      "ok" if exists else "missing",
            "path":        str(repo_path),
            "url":         info["url"],
            "description": info["description"],
            "size":        _fmt_size(size) if size else "—",
        }
    return results


def ok_count(results: dict) -> int:
    return sum(1 for v in results.values() if v["status"] == "ok")


async def check_services() -> list[dict]:
    """Async ping of each known repo's service port. Returns list of repo dicts."""
    import asyncio
    import httpx as _httpx

    _META: list[tuple[str, int | None, str]] = [
        ("AI-Youtube-Shorts-Generator", None,  "Shorts pipeline"),
        ("Pixelle-Video",               8080,  "Video generation"),
        ("ComfyUI",                     8188,  "Stable Diffusion UI"),
        ("stable-diffusion-webui",      7860,  "SD AUTOMATIC1111"),
        ("GPT-SoVITS",                  9880,  "Neural voice cloning"),
        ("F5-TTS",                      None,  "F5-TTS synthesis"),
        ("chatterbox",                  None,  "Chatterbox TTS"),
        ("kokoro",                      None,  "Kokoro TTS"),
        ("faster-whisper",              None,  "Fast Whisper"),
        ("ShortGPT",                    None,  "Short video AI"),
        ("TTS",                         None,  "Coqui TTS"),
        ("n8n-mcp",                     5678,  "n8n automation"),
        ("yt-dlp",                      None,  "Video downloader"),
        ("open-webui",                  3000,  "Open WebUI"),
        ("moviepy",                     None,  "Python video editing"),
    ]
    result_list = [
        {"name": m[0], "path": str(AI_REPOS_DIR / m[0]),
         "ok": (AI_REPOS_DIR / m[0]).exists(),
         "port": m[1], "description": m[2]}
        for m in _META
    ]
    serviced = [r for r in result_list if r["port"]]

    async def _ping(repo: dict) -> dict:
        try:
            async with _httpx.AsyncClient(timeout=2) as c:
                r = await c.get(f"http://localhost:{repo['port']}")
                repo["running"] = r.status_code < 500
        except Exception:
            repo["running"] = False
        return repo

    pinged = await asyncio.gather(*[_ping(r) for r in serviced], return_exceptions=True)
    running_map = {r["name"]: r.get("running", False) for r in pinged if isinstance(r, dict)}
    for repo in result_list:
        repo["running"] = running_map.get(repo["name"], None if repo["port"] is None else False)
    return result_list


def _dir_size(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def _fmt_size(size: int) -> str:
    if size >= 1_073_741_824: return f"{size/1_073_741_824:.1f} GB"
    if size >= 1_048_576:     return f"{size/1_048_576:.1f} MB"
    if size >= 1024:           return f"{size/1024:.1f} KB"
    return f"{size} B"
