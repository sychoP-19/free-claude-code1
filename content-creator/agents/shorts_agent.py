"""Shorts agent — wraps the AI-Youtube-Shorts-Generator pipeline."""
import asyncio
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Make the external shorts generator importable
_SHORTS_GEN_ROOT = Path(__file__).parent.parent.parent / "AI-Youtube-Shorts-Generator"
if _SHORTS_GEN_ROOT.exists() and str(_SHORTS_GEN_ROOT) not in sys.path:
    sys.path.insert(0, str(_SHORTS_GEN_ROOT))


async def run(
    url: str,
    num_clips: int = 3,
    aspect_ratio: str = "9:16",
    mode: str = "local",
    quality: str = "720",
) -> dict:
    if not url:
        raise ValueError("YouTube URL is required")

    loop = asyncio.get_event_loop()

    if mode == "api":
        return await _run_api_mode(url, num_clips, aspect_ratio)

    return await loop.run_in_executor(None, _run_local, url, num_clips, aspect_ratio, quality)


def _run_local(url: str, num_clips: int, aspect_ratio: str, quality: str) -> dict:
    try:
        from shorts_generator.pipeline import generate_shorts
        result = generate_shorts(
            youtube_url=url,
            num_clips=num_clips,
            aspect_ratio=aspect_ratio,
            download_format=quality,
            mode="local",
        )
        return _normalise(result)
    except ImportError:
        logger.warning("AI-Youtube-Shorts-Generator not found — using fallback stub")
        return _stub(url, num_clips)
    except Exception as e:
        logger.error("Shorts pipeline error: %s", e)
        raise


async def _run_api_mode(url: str, num_clips: int, aspect_ratio: str) -> dict:
    import httpx
    api_key = __import__("os").environ.get("MUAPI_KEY", "")
    if not api_key:
        raise RuntimeError("MUAPI_KEY not set — cannot use API mode")
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            "https://api.muapi.io/v1/shorts",
            json={"url": url, "num_clips": num_clips, "aspect_ratio": aspect_ratio},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        return _normalise(r.json())


def _normalise(raw: dict) -> dict:
    shorts = raw.get("shorts") or raw.get("clips") or raw.get("results") or []
    normalised = []
    for item in shorts:
        normalised.append({
            "start":    item.get("start", 0),
            "end":      item.get("end", 0),
            "score":    round(float(item.get("score", 0)), 2),
            "reason":   item.get("reason") or item.get("highlight_reason", ""),
            "path":     item.get("path") or item.get("output_path", ""),
            "clip_url": item.get("clip_url", ""),
        })
    return {"shorts": normalised, "source_url": raw.get("url", ""), "total": len(normalised)}


def _stub(url: str, num_clips: int) -> dict:
    return {
        "shorts": [
            {"start": i * 60, "end": i * 60 + 45, "score": round(0.9 - i * 0.1, 2),
             "reason": "High-energy segment detected", "path": "", "clip_url": ""}
            for i in range(num_clips)
        ],
        "source_url": url,
        "total": num_clips,
        "_stub": True,
    }
