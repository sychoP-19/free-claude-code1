"""pipelines/avatar_reel_batch.py - Batch avatar reel production.

Generates trendy female avatar reel videos from niche themes:
  1. Downloads avatar images from Pollinations (free, no key)
  2. Creates short narration scripts per reel (15-30s)
  3. Generates TTS audio (gTTS -> pyttsx3 -> ffmpeg fallback)
  4. Assembles 1080x1920 MP4 with optional background beat
  5. Outputs to outputs/reels/{slug}/video.mp4

Usage:
  from pipelines.avatar_reel_batch import AvatarReelBatchPipeline
  result = await AvatarReelBatchPipeline(params).run()

Or via the convenience wrapper:
  result = await run({"topics": ["tech AI", "luxury", "fitness"], "count": 3})
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import re
import shutil
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from pipelines.base import PipelineRun, OUTPUTS, build_system_prompt, slugify
from pipelines.llm import chat

logger = logging.getLogger(__name__)

_W, _H = 1080, 1920
_MIN_VIDEO_BYTES = 100_000

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"
AVATAR_PROMPT_TEMPLATE = (
    "trendy female digital avatar, {niche} theme, cyberpunk aesthetic, "
    "glowing neon, professional, 4k, portrait"
)

# Scene-level augmentation phrases cycled per scene to add variety
_SCENE_AUGMENTS = [
    "close-up face, holographic visor, dynamic lighting",
    "full body pose, neon city background, bokeh",
    "side profile, digital rain, blue-pink palette",
    "three-quarter view, augmented reality overlays, sharp focus",
    "dramatic angle, light trails, studio quality",
]


async def _run_ffmpeg(argv: list[str], timeout: float = 120) -> tuple[int, bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, b"", b"timeout"
    return proc.returncode or 0, stdout, stderr


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/Arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _create_fallback_avatar(niche: str, idx: int, out_path: Path) -> None:
    """Generate a Pillow-based avatar when Pollinations fails."""
    gradients = [
        ((8, 8, 25), (0, 30, 80)),
        ((20, 5, 30), (60, 0, 80)),
        ((5, 20, 15), (0, 70, 50)),
        ((25, 8, 5), (80, 20, 0)),
        ((5, 15, 30), (0, 50, 100)),
    ]
    accents = [
        (0, 200, 255),
        (180, 80, 255),
        (0, 255, 180),
        (255, 160, 0),
        (80, 160, 255),
    ]
    top, bot = gradients[idx % len(gradients)]
    accent = accents[idx % len(accents)]
    img = Image.new("RGB", (_W, _H))
    draw = ImageDraw.Draw(img)
    for y in range(_H):
        t = y / (_H - 1)
        r = int(top[0] + (bot[0] - top[0]) * t)
        g = int(top[1] + (bot[1] - top[1]) * t)
        b = int(top[2] + (bot[2] - top[2]) * t)
        draw.line([(0, y), (_W, y)], fill=(r, g, b))
    # Centered niche label
    title_font = _load_font(64)
    sub_font = _load_font(36)
    label = niche.title()
    bbox = draw.textbbox((0, 0), label, font=title_font)
    tw = bbox[2] - bbox[0]
    x = (_W - tw) // 2
    draw.text((x + 3, _H // 2 - 77), label, font=title_font, fill=(0, 0, 0))
    draw.text((x, _H // 2 - 80), label, font=title_font, fill=(255, 255, 255))
    sub = "AI AVATAR REEL"
    bbox2 = draw.textbbox((0, 0), sub, font=sub_font)
    sw = bbox2[2] - bbox2[0]
    sx = (_W - sw) // 2
    draw.text((sx, _H // 2), sub, font=sub_font, fill=accent)
    # Accent line
    y_line = _H // 2 + 50
    draw.rectangle([100, y_line, _W - 100, y_line + 4], fill=accent)
    img.save(str(out_path), "PNG")


async def _download_avatar(
    client: "httpx.AsyncClient",
    niche: str,
    idx: int,
    seed: int,
    out_path: Path,
) -> bool:
    """Download avatar image from Pollinations. Returns True on success."""
    augment = _SCENE_AUGMENTS[idx % len(_SCENE_AUGMENTS)]
    prompt = f"{AVATAR_PROMPT_TEMPLATE.format(niche=niche)}, {augment}"
    encoded = prompt.replace(" ", "%20").replace("\n", "%0A")
    url = (
        f"{POLLINATIONS_BASE}/{encoded}"
        f"?model=flux&width={_W}&height={_H}"
        f"&seed={seed}&nologo=true&enhance=true"
    )
    try:
        resp = await client.get(url, timeout=60, follow_redirects=True)
        if resp.status_code == 200 and len(resp.content) > 1024:
            out_path.write_bytes(resp.content)
            return True
        logger.warning("Pollinations HTTP %s for seed %s", resp.status_code, seed)
    except Exception as e:
        logger.warning("Pollinations download failed: %s", e)
    return False


async def _generate_script_sentences(topic: str, num_scenes: int) -> list[str]:
    """Generate short narration sentences via LLM with offline fallback."""
    parts = [
        f"Write exactly {num_scenes} punchy viral short-video sentences for: {topic}.",
        "Each sentence is one scene (15-30 words). Hook first, CTA last.",
        f"Return ONLY a JSON array of {num_scenes} strings. No extra text.",
    ]
    prompt = " ".join(parts)
    try:
        reply = await chat(
            [{"role": "user", "content": prompt}],
            system=build_system_prompt("viral content writer"),
            max_tokens=600,
            temperature=0.8,
        )
        m = re.search(r"\[.*\]", reply, re.DOTALL)
        if m:
            try:
                arr = json.loads(m.group())
                sentences = [str(s).strip() for s in arr if str(s).strip()]
                if len(sentences) >= num_scenes:
                    return sentences[:num_scenes]
            except Exception:
                pass
        lines = [ln.strip().strip('"') for ln in reply.splitlines() if ln.strip()]
        sentences = [ln for ln in lines if len(ln) > 10][:num_scenes]
        while len(sentences) < num_scenes:
            sentences.append(f"Learn more about {topic} - follow for daily insights.")
        return sentences
    except Exception:
        return _offline_script(topic, num_scenes)


def _offline_script(topic: str, num_scenes: int) -> list[str]:
    words = topic.replace("-", " ").replace("_", " ").title()
    templates = [
        f"You won't believe how {words} is changing everything right now!",
        f"Here's what nobody tells you about {words} -- and it's mind-blowing.",
        f"The secret behind {words} that experts don't want you to know.",
        f"If you're not using {words} yet, you're already falling behind.",
        f"{words} is the future -- and the future is already here.",
        f"Most people get {words} completely wrong. Here's what actually works.",
        f"Follow for more {words} insights!",
    ]
    return [templates[i % len(templates)] for i in range(num_scenes)]


async def _make_tts_audio(text: str, out_path: Path) -> bool:
    """Generate TTS audio. Tries gTTS, pyttsx3, then ffmpeg sine-tone."""
    loop = asyncio.get_event_loop()

    def _gtts_sync() -> None:
        from gtts import gTTS
        tts = gTTS(text=text, lang="en", slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        out_path.write_bytes(buf.getvalue())

    try:
        await loop.run_in_executor(None, _gtts_sync)
        if out_path.exists() and out_path.stat().st_size > 0:
            return True
    except Exception:
        pass

    def _pyttsx_sync() -> None:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 165)
        engine.setProperty("volume", 0.95)
        engine.save_to_file(text, str(out_path))
        engine.runAndWait()

    try:
        await loop.run_in_executor(None, _pyttsx_sync)
        if out_path.exists() and out_path.stat().st_size > 0:
            return True
    except Exception:
        pass

    # Fallback: ffmpeg sine tone
    words = len(text.split())
    duration = max(3.0, words * 0.35)
    argv = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration:.1f}",
        "-c:a", "aac", "-b:a", "64k",
        str(out_path),
    ]
    import subprocess
    subprocess.run(argv, capture_output=True, timeout=30)
    return out_path.exists() and out_path.stat().st_size > 0


async def _audio_duration(path: Path) -> float:
    argv = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(path)]
    rc, stdout, _ = await _run_ffmpeg(argv, timeout=30)
    if rc != 0:
        return 4.0
    try:
        data = json.loads(stdout)
        for s in data.get("streams", []):
            dur = float(s.get("duration", 0))
            if dur > 0:
                return dur
    except Exception:
        pass
    return 4.0


async def _make_clip(image_path: Path, audio_path: Path, out_path: Path, duration: float) -> bool:
    argv = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(image_path),
        "-i", str(audio_path),
        "-c:v", "libx264", "-tune", "stillimage",
        "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-t", f"{duration:.2f}",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-vf", f"scale={_W}:{_H}",
        str(out_path),
    ]
    rc, _, _ = await _run_ffmpeg(argv, timeout=120)
    return rc == 0 and out_path.exists() and out_path.stat().st_size > 0


async def _generate_bgm(out_path: Path, duration: float) -> bool:
    dur_str = f"{duration:.1f}"
    fade_st = f"{max(0.0, duration - 2.0):.1f}"
    filt = (
        f"[0][1]amix=inputs=2:duration=first,volume=0.04,"
        f"afade=t=in:ss=0:d=2,afade=t=out:st={fade_st}:d=2"
    )
    argv = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"sine=frequency=220:duration={dur_str}",
        "-f", "lavfi", "-i", f"sine=frequency=330:duration={dur_str}",
        "-filter_complex", filt,
        "-c:a", "aac", "-b:a", "64k",
        str(out_path),
    ]
    rc, _, _ = await _run_ffmpeg(argv, timeout=60)
    return rc == 0 and out_path.exists() and out_path.stat().st_size > 0


async def _produce_single_reel(
    niche: str,
    reel_idx: int,
    out_dir: Path,
    num_scenes: int,
    pollinations_client: "httpx.AsyncClient",
    tmp_dir: Path,
    emit_fn,
) -> dict:
    """Produce a single avatar reel. Returns result dict."""
    started = time.time()
    slug = slugify(niche) + f"_{reel_idx}"
    reel_dir = out_dir / slug
    reel_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate script
    await emit_fn("writer", "act", f"Generating script for: {niche}")
    sentences = await _generate_script_sentences(niche, num_scenes)
    await emit_fn("writer", "done", f"Script ready: {len(sentences)} scenes")

    # 2. Download avatar images + TTS per scene + build clips
    clip_paths: list[Path] = []
    total_duration = 0.0

    for i, sentence in enumerate(sentences):
        await emit_fn("designer", "act", f"Reel {reel_idx+1} scene {i+1}/{num_scenes}")

        img_path = tmp_dir / f"reel{reel_idx}_scene_{i:02d}.png"
        audio_path = tmp_dir / f"reel{reel_idx}_scene_{i:02d}.mp3"
        clip_path = reel_dir / f"clip_{i:02d}.mp4"

        seed = reel_idx * 10000 + i * 1000 + int(time.time()) % 1000
        ok = await _download_avatar(pollinations_client, niche, i, seed, img_path)
        if not ok:
            _create_fallback_avatar(niche, i, img_path)

        if not img_path.exists():
            raise RuntimeError(f"Image generation failed for reel {reel_idx+1} scene {i+1}")

        tts_ok = await _make_tts_audio(sentence, audio_path)
        if not tts_ok or not audio_path.exists() or audio_path.stat().st_size == 0:
            raise RuntimeError(f"TTS failed for reel {reel_idx+1} scene {i+1}")

        dur = await _audio_duration(audio_path)
        dur = max(2.0, dur + 0.5)
        total_duration += dur

        clip_ok = await _make_clip(img_path, audio_path, clip_path, dur)
        if not clip_ok:
            raise RuntimeError(f"ffmpeg clip failed for reel {reel_idx+1} scene {i+1}")

        clip_paths.append(clip_path)

    # 3. Concatenate clips
    concat_file = tmp_dir / f"reel{reel_idx}_concat.txt"
    lines_txt = []
    for p in clip_paths:
        safe_p = str(p).replace("\\", "/")
        lines_txt.append("file '" + safe_p + "'\n")
    concat_file.write_text("".join(lines_txt), encoding="utf-8")

    concat_out = reel_dir / "concat_raw.mp4"
    rc, _, stderr = await _run_ffmpeg([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(concat_out),
    ], timeout=180)
    if rc != 0 or not concat_out.exists() or concat_out.stat().st_size == 0:
        err = stderr.decode(errors="ignore")[:300]
        raise RuntimeError(f"concat failed: {err}")

    # 4. Add background music
    bgm_path = tmp_dir / f"reel{reel_idx}_bgm.aac"
    has_bgm = await _generate_bgm(bgm_path, total_duration + 2)
    final_out = reel_dir / "video.mp4"

    if has_bgm:
        rc, _, _ = await _run_ffmpeg([
            "ffmpeg", "-y",
            "-i", str(concat_out),
            "-i", str(bgm_path),
            "-filter_complex",
            "[0:a][1:a]amix=inputs=2:duration=first:weights=1 0.3[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(final_out),
        ], timeout=240)
        if rc != 0 or not final_out.exists() or final_out.stat().st_size == 0:
            shutil.copy2(str(concat_out), str(final_out))
    else:
        shutil.copy2(str(concat_out), str(final_out))

    if not final_out.exists() or final_out.stat().st_size < _MIN_VIDEO_BYTES:
        size = final_out.stat().st_size if final_out.exists() else 0
        raise RuntimeError(f"Final video too small or missing: {size} bytes (need >{_MIN_VIDEO_BYTES:,})")

    elapsed = time.time() - started
    return {
        "ok": True,
        "niche": niche,
        "output_path": str(final_out),
        "clips": len(clip_paths),
        "duration_s": round(total_duration, 1),
        "size_bytes": final_out.stat().st_size,
        "elapsed_s": round(elapsed, 1),
    }


class AvatarReelBatchPipeline(PipelineRun):
    """Batch avatar reel production pipeline.

    Params:
        topics: list[str] - Niche themes (e.g. ["tech AI", "luxury", "fitness"])
        count: int - Number of reels per topic (default 1)
        num_scenes: int - Scenes per reel (default 3, max 6)
        model: str - Pollinations model (default "flux")
    """
    pipeline = "avatar_reel_batch"
    publish_platforms = ("youtube-shorts", "tiktok", "instagram")

    async def execute(self) -> tuple[str, dict]:
        import httpx
        import tempfile

        topics: list[str] = self.params.get("topics", [])
        if not topics:
            raise ValueError("'topics' list is required")

        count = max(1, min(5, int(self.params.get("count", 1))))
        num_scenes = max(2, min(6, int(self.params.get("num_scenes", 3))))

        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg not found on PATH")

        reels_dir = OUTPUTS / "reels"
        reels_dir.mkdir(parents=True, exist_ok=True)

        results: list[dict] = []
        all_errors: list[str] = []
        total_reels = len(topics) * count

        with tempfile.TemporaryDirectory(prefix="arb_") as tmp:
            tmp_path = Path(tmp)

            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                reel_idx = 0
                for topic in topics:
                    for copy_num in range(count):
                        reel_idx += 1
                        pct = int((reel_idx / total_reels) * 100)
                        await self.set_stage("production", pct)

                        try:
                            result = await _produce_single_reel(
                                niche=topic,
                                reel_idx=reel_idx,
                                out_dir=reels_dir,
                                num_scenes=num_scenes,
                                pollinations_client=client,
                                tmp_dir=tmp_path,
                                emit_fn=self.emit,
                            )
                            results.append(result)
                            self.track_asset(
                                kind="video",
                                path=result["output_path"],
                                caption=f"Avatar reel: {topic}",
                                tags=["avatar_reel", slugify(topic)],
                            )
                        except Exception as e:
                            msg = f"{type(e).__name__}: {e}"
                            all_errors.append(msg)
                            await self.emit("producer", "error", f"Reel '{topic}' #{copy_num+1} failed: {msg}")
                            results.append({"ok": False, "niche": topic, "error": msg})

        # Determine primary output path (first successful reel)
        primary = ""
        for r in results:
            if r.get("ok") and r.get("output_path"):
                primary = r["output_path"]
                break

        summary = {
            "total_requested": total_reels,
            "total_ok": sum(1 for r in results if r.get("ok")),
            "total_failed": sum(1 for r in results if not r.get("ok")),
            "reels": results,
            "errors": all_errors,
        }

        return primary, summary


async def run(params: dict) -> dict:
    """Convenience wrapper for running the batch pipeline."""
    result = await AvatarReelBatchPipeline(params).run()
    return result.__dict__
