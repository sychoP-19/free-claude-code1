"""Media Lab agent — yt-dlp download + Whisper transcription + clip extraction."""
import asyncio
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

DOWNLOADS_DIR = Path(__file__).parent.parent / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

WHISPER_SRV = os.environ.get("WHISPER_SERVER", "http://localhost:9000")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")


async def download_video(url: str, quality: str = "720", audio_only: bool = False) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _download_sync, url, quality, audio_only)


def _download_sync(url: str, quality: str, audio_only: bool) -> dict:
    out_tmpl = str(DOWNLOADS_DIR / "%(title).60s-%(id)s.%(ext)s")
    cmd = ["yt-dlp", "--no-playlist", "--write-info-json", "-o", out_tmpl]
    if audio_only:
        cmd += ["-x", "--audio-format", "mp3"]
    else:
        cmd += ["-f", f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best"]
    cmd.append(url)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(result.stderr[-500:] if result.stderr else "yt-dlp failed")

        # Find downloaded file
        info_files = list(DOWNLOADS_DIR.glob("*.info.json"))
        if info_files:
            latest = max(info_files, key=lambda f: f.stat().st_mtime)
            info = json.loads(latest.read_text(encoding="utf-8", errors="ignore"))
            media_file = latest.with_suffix("").with_suffix("." + info.get("ext", "mp4"))
            return {
                "title":    info.get("title", ""),
                "duration": info.get("duration", 0),
                "channel":  info.get("channel", ""),
                "views":    info.get("view_count", 0),
                "path":     str(media_file),
                "filename": media_file.name,
                "size_mb":  round(media_file.stat().st_size / 1_048_576, 1) if media_file.exists() else 0,
            }
        return {"path": "", "error": "Could not locate downloaded file"}
    except subprocess.TimeoutExpired:
        raise RuntimeError("Download timed out after 5 minutes")


async def transcribe_file(file_path: str, language: str = "auto") -> dict:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Try local whisper server first
    try:
        return await _transcribe_whisper_server(path, language)
    except Exception as e:
        logger.debug("Whisper server unavailable: %s", e)

    # Try OpenAI Whisper API
    if OPENAI_KEY:
        return await _transcribe_openai(path, language)

    # Try local whisper CLI
    return await _transcribe_local_cli(path, language)


async def _transcribe_whisper_server(path: Path, language: str) -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        with open(path, "rb") as f:
            params = {} if language == "auto" else {"language": language}
            r = await client.post(f"{WHISPER_SRV}/asr", files={"audio_file": f}, params=params)
            r.raise_for_status()
            data = r.json()
            return _normalise_transcript(data)


async def _transcribe_openai(path: Path, language: str) -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        headers = {"Authorization": f"Bearer {OPENAI_KEY}"}
        with open(path, "rb") as f:
            files = {"file": (path.name, f, "audio/mpeg"), "model": (None, "whisper-1")}
            if language != "auto":
                files["language"] = (None, language)
            r = await client.post("https://api.openai.com/v1/audio/transcriptions", headers=headers, files=files)
            r.raise_for_status()
            data = r.json()
            return _normalise_transcript(data)


async def _transcribe_local_cli(path: Path, language: str) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _whisper_cli_sync, path, language)


def _whisper_cli_sync(path: Path, language: str) -> dict:
    cmd = ["python3", "-m", "whisper", str(path), "--output_format", "json", "--output_dir", str(DOWNLOADS_DIR)]
    if language != "auto":
        cmd += ["--language", language]
    try:
        subprocess.run(cmd, capture_output=True, timeout=300, check=True)
        json_path = DOWNLOADS_DIR / (path.stem + ".json")
        if json_path.exists():
            data = json.loads(json_path.read_text())
            return _normalise_transcript(data)
    except Exception as e:
        raise RuntimeError(f"Local Whisper failed: {e}")
    return {"text": "", "segments": [], "language": language}


def _normalise_transcript(raw: dict) -> dict:
    segments = raw.get("segments", [])
    text = raw.get("text", "") or " ".join(s.get("text", "") for s in segments)
    return {
        "text": text.strip(),
        "language": raw.get("language", ""),
        "duration": raw.get("duration", 0),
        "segments": [
            {
                "start": round(float(s.get("start", 0)), 2),
                "end":   round(float(s.get("end", 0)), 2),
                "text":  s.get("text", "").strip(),
            }
            for s in segments
        ],
        "word_count": len(text.split()),
    }


async def extract_audio(video_path: str) -> str:
    audio_path = str(Path(video_path).with_suffix(".mp3"))
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _ffmpeg_extract, video_path, audio_path)
    return audio_path


def _ffmpeg_extract(video: str, audio: str) -> None:
    subprocess.run(["ffmpeg", "-i", video, "-vn", "-ar", "16000", "-ac", "1", "-y", audio],
                   capture_output=True, check=True, timeout=120)
