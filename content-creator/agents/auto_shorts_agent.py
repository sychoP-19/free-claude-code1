"""auto_shorts_agent.py — thin compatibility wrapper.

Real implementation lives in pipelines/shorts.py (yt-dlp + Whisper + ffmpeg).
This module is kept for backward compatibility with the existing /api/shorts/auto
route. It returns structured results so the UI cannot mistake an empty file
for success.

NEW: Extends to support Stage 3-4 pipeline via asset_generator and video_assembler.
"""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

import httpx

_OUTPUTS = Path(__file__).parent.parent / "outputs"
_OBAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


async def generate(topic: str, model: str = "llama3.1:8b") -> dict:
    """Topic → Ollama script → Pollinations images → gTTS audio → moviepy MP4.

    Returns a structured result with ok/error fields so the UI surfaces failures
    rather than reporting success on an empty file.
    """
    _OUTPUTS.mkdir(exist_ok=True)
    started = time.time()

    script_res = await _ollama_script(topic, model)
    if not script_res["ok"]:
        return _fail("script", script_res["error"], topic, started)

    scenes = _split_scenes(script_res["text"])
    img_res = await _fetch_images(scenes)
    if not img_res["paths"]:
        return _fail("images", "no images downloaded (Pollinations unreachable)", topic, started, script=script_res["text"])

    audio_res = _gtts_audio(script_res["text"])
    if not audio_res["ok"]:
        return _fail("audio", audio_res["error"], topic, started, script=script_res["text"], images=img_res["paths"])

    video_res = _assemble_video(img_res["paths"], audio_res["path"], topic)
    if not video_res["ok"]:
        return _fail("assemble", video_res["error"], topic, started, script=script_res["text"], images=img_res["paths"], audio=audio_res["path"])

    return {
        "ok": True,
        "stage": "complete",
        "topic": topic,
        "script": script_res["text"],
        "scenes": scenes,
        "images": img_res["paths"],
        "audio": audio_res["path"],
        "video": video_res["path"],
        "bytes": video_res["bytes"],
        "elapsed_s": round(time.time() - started, 1),
    }


async def generate_with_pipeline(topic: str, script_text: str | None = None) -> dict:
    """NEW: Use Stage 3-4 pipeline for asset generation and video assembly.

    This wraps the new reel_production pipeline for better error handling and
    fallback support (Pollinations → stock footage → placeholder).

    Args:
        topic: Topic name (used as topic_id)
        script_text: Optional pre-generated script (if None, generates via Ollama)

    Returns:
        Pipeline result with asset paths and final video
    """
    started = time.time()

    # Generate script if not provided
    if not script_text:
        script_res = await _ollama_script(topic, "llama3")
        if not script_res["ok"]:
            return _fail("script", script_res["error"], topic, started)
        script_text = script_res["text"]

    scenes = _split_scenes(script_text)

    try:
        from pipelines.reel_production import run as reel_production_run

        result = await reel_production_run({
            "topic_id": topic,
            "scenes": scenes,
            "script": script_text,
            "n_images_per_scene": 5,
            "width": 1080,
            "height": 1920,
            "clip_duration": 3.0,
        })

        elapsed = time.time() - started

        return {
            "ok": result.get("ok", False),
            "stage": "complete" if result.get("ok") else "failed",
            "topic": topic,
            "scenes": scenes,
            "script": script_text,
            "assets": result.get("assets", []),
            "output_path": result.get("output_path", ""),
            "elapsed_s": round(elapsed, 1),
            **(result.get("extra", {}) if isinstance(result.get("extra"), dict) else {}),
        }

    except Exception as e:
        return _fail("pipeline", f"{type(e).__name__}: {e}", topic, started)


def _fail(stage: str, error: str, topic: str, started: float, **rest) -> dict:
    return {
        "ok": False,
        "stage": stage,
        "error": error,
        "topic": topic,
        "elapsed_s": round(time.time() - started, 1),
        **rest,
    }


async def _ollama_script(topic: str, model: str) -> dict:
    prompt = (
        f"Write a punchy 60-second YouTube Shorts script about: {topic}.\n"
        "Format: exactly 10 short sentences. No hashtags. No emojis. "
        "Each sentence is one scene. Make it viral and engaging."
    )
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{_OBAMA_URL}/api/chat",
                json={
                    "model": model,
                    "stream": False,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            r.raise_for_status()
            text = (r.json().get("message") or {}).get("content", "").strip()
            if not text:
                return {"ok": False, "error": "ollama returned empty content", "text": ""}
            return {"ok": True, "text": text}
    except httpx.ConnectError:
        return {"ok": False, "error": f"ollama at {_OBAMA_URL} unreachable", "text": ""}
    except Exception as e:
        return {"ok": False, "error": f"ollama: {type(e).__name__}: {e}", "text": ""}


def _split_scenes(script: str, n: int = 5) -> list[str]:
    sentences = [s.strip() for s in script.replace("\n", " ").split(".") if s.strip()]
    if not sentences:
        if not script.strip():
            return []
        sentences = [script]
    step = max(1, len(sentences) // n)
    return [sentences[i] for i in range(0, min(len(sentences), n * step), step)][:n]


async def _fetch_images(scenes: list[str]) -> dict:
    paths: list[str] = []
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=60) as client:
        tasks = [_download_image(client, scene, i) for i, scene in enumerate(scenes)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, dict) and r.get("ok"):
            paths.append(r["path"])
        elif isinstance(r, dict):
            errors.append(r.get("error", "unknown"))
        else:
            errors.append(f"{type(r).__name__}: {r}")
    return {"paths": paths, "errors": errors}


async def _download_image(client: httpx.AsyncClient, scene: str, idx: int) -> dict:
    safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in scene[:80])
    encoded = safe.replace(" ", "%20")
    full_url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?model=flux&width=1080&height=1920&seed={idx * 42 + 1}&nologo=true&enhance=true"
    )
    path = _OUTPUTS / f"scene_{idx}.jpg"
    try:
        r = await client.get(full_url, follow_redirects=True, timeout=60)
        if r.status_code != 200:
            return {"ok": False, "error": f"HTTP {r.status_code}"}
        if not r.content or len(r.content) < 1024:
            return {"ok": False, "error": f"image too small ({len(r.content)} bytes)"}
        path.write_bytes(r.content)
        return {"ok": True, "path": str(path), "bytes": len(r.content)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _gtts_audio(script: str) -> dict:
    path = _OUTPUTS / f"narration_{int(time.time())}.mp3"
    try:
        from gtts import gTTS
    except ImportError:
        return {"ok": False, "error": "gTTS not installed — run: uv pip install gTTS"}
    try:
        tts = gTTS(text=script, lang="en", slow=False)
        tts.save(str(path))
        size = path.stat().st_size if path.exists() else 0
        if size < 1024:
            return {"ok": False, "error": f"gTTS produced {size}-byte file"}
        return {"ok": True, "path": str(path), "bytes": size}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _assemble_video(images: list[str], audio_path: str, topic: str) -> dict:
    out = _OUTPUTS / f"short_{int(time.time())}.mp4"
    valid_images = [p for p in images if p and Path(p).exists() and Path(p).stat().st_size > 1024]
    if not valid_images:
        return {"ok": False, "error": "no valid image files (all empty or missing)"}
    try:
        from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
    except ImportError:
        return {"ok": False, "error": "moviepy not installed — run: uv pip install 'moviepy==1.0.3'"}
    try:
        clips = [ImageClip(p).set_duration(3) for p in valid_images]
        video = concatenate_videoclips(clips, method="compose")
        if audio_path and Path(audio_path).exists():
            audio = AudioFileClip(audio_path)
            duration = min(video.duration, audio.duration)
            video = video.subclip(0, duration).set_audio(audio.subclip(0, duration))
        video.write_videofile(str(out), fps=24, codec="libx264", audio_codec="aac", logger=None)
        size = out.stat().st_size if out.exists() else 0
        if size < 10_000:
            return {"ok": False, "error": f"moviepy wrote {size}-byte file — ffmpeg may be misconfigured"}
        return {"ok": True, "path": str(out), "bytes": size}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
