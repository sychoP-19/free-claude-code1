"""pipelines/auto_video.py - topic -> complete short video.

Flow: LLM script -> Pillow images -> gTTS audio -> ffmpeg clips -> concat -> BGM
Output: outputs/auto_video/<slug>/video.mp4
"""
from __future__ import annotations

import asyncio
import io
import json
import re
import shutil
import tempfile
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS

from pipelines.base import PipelineRun, OUTPUTS, build_system_prompt, slugify
from pipelines.llm import chat

_W, _H = 1080, 1920

_SCENE_GRADIENTS = [
    ((8, 8, 25),   (0, 30, 80)),
    ((20, 5, 30),  (60, 0, 80)),
    ((5, 20, 15),  (0, 70, 50)),
    ((25, 8, 5),   (80, 20, 0)),
    ((5, 15, 30),  (0, 50, 100)),
]
_SCENE_ACCENTS = [
    (0, 200, 255),
    (180, 80, 255),
    (0, 255, 180),
    (255, 160, 0),
    (80, 160, 255),
]
_WHITE = (255, 255, 255)


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


def _gradient_image(top_rgb, bot_rgb, accent, idx, total):
    img = Image.new("RGB", (_W, _H))
    draw = ImageDraw.Draw(img)
    for y in range(_H):
        t = y / (_H - 1)
        r = int(top_rgb[0] + (bot_rgb[0] - top_rgb[0]) * t)
        g = int(top_rgb[1] + (bot_rgb[1] - top_rgb[1]) * t)
        b = int(top_rgb[2] + (bot_rgb[2] - top_rgb[2]) * t)
        draw.line([(0, y), (_W, y)], fill=(r, g, b))
    for x in range(_W):
        t = abs(x / _W * 2 - 1)
        a_val = int(255 * (1 - t * 0.6))
        r2 = int(accent[0] * a_val / 255)
        g2 = int(accent[1] * a_val / 255)
        b2 = int(accent[2] * a_val / 255)
        draw.line([(x, 0), (x, 6)], fill=(r2, g2, b2))
    dot_r, dot_gap = 10, 30
    total_w = total * (dot_r * 2) + (total - 1) * dot_gap
    start_x = (_W - total_w) // 2
    y_dot = _H - 60
    for i in range(total):
        x = start_x + i * (dot_r * 2 + dot_gap)
        color = accent if i == idx else (60, 70, 80)
        draw.ellipse([x, y_dot, x + dot_r * 2, y_dot + dot_r * 2], fill=color)
    return img


def _load_font(size):
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


def _render_text(img, text, accent, scene_num):
    draw = ImageDraw.Draw(img)
    draw.text((60, 70), f"#{scene_num}", font=_load_font(48), fill=accent)
    body_font = _load_font(72)
    lines = textwrap.wrap(text, width=22)
    line_h = 90
    total_h = len(lines) * line_h
    y_start = (_H - total_h) // 2 - 80
    for i, line in enumerate(lines):
        y = y_start + i * line_h
        draw.text((62, y + 4), line, font=body_font, fill=(0, 0, 0))
        draw.text((60, y), line, font=body_font, fill=_WHITE)
    y_line = y_start + total_h + 20
    draw.rectangle([60, y_line, _W - 60, y_line + 4], fill=accent)
    return img


async def _make_scene_image(text, idx, total, out_path):
    grad_top, grad_bot = _SCENE_GRADIENTS[idx % len(_SCENE_GRADIENTS)]
    accent = _SCENE_ACCENTS[idx % len(_SCENE_ACCENTS)]
    img = _gradient_image(grad_top, grad_bot, accent, idx, total)
    img = _render_text(img, text, accent, idx + 1)
    img.save(str(out_path), "PNG")


async def _make_tts_audio(text, out_path):
    """Generate TTS audio. Tries gTTS (needs internet) first, falls back to
    pyttsx3 (offline Windows SAPI), then to ffmpeg sine-tone placeholder."""
    loop = asyncio.get_event_loop()

    # 1) gTTS (best quality, needs network)
    def _gtts():
        tts = gTTS(text=text, lang="en", slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        out_path.write_bytes(buf.getvalue())

    try:
        await loop.run_in_executor(None, _gtts)
        if out_path.exists() and out_path.stat().st_size > 0:
            return
    except Exception:
        pass

    # 2) pyttsx3 — offline Windows SAPI TTS
    def _pyttsx():
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 165)
        engine.setProperty("volume", 0.95)
        engine.save_to_file(text, str(out_path))
        engine.runAndWait()

    try:
        await loop.run_in_executor(None, _pyttsx)
        if out_path.exists() and out_path.stat().st_size > 0:
            return
    except Exception:
        pass

    # 3) ffmpeg sine-tone placeholder — always works
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


async def _audio_duration(path):
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


async def _make_clip(image_path, audio_path, out_path, duration):
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


async def _generate_bgm(out_path, duration):
    dur_str = f"{duration:.1f}"
    fade_st = f"{max(0.0, duration - 2.0):.1f}"
    filt = f"[0][1]amix=inputs=2:duration=first,volume=0.04,afade=t=in:ss=0:d=2,afade=t=out:st={fade_st}:d=2"
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


def _offline_script(topic: str, num_scenes: int) -> list[str]:
    """Template-based fallback script — no LLM required."""
    words = topic.replace("-", " ").replace("_", " ").title()
    templates = [
        f"🔥 You won't believe how {words} is changing everything right now!",
        f"Here's what nobody tells you about {words} — and it's mind-blowing.",
        f"The secret behind {words} that experts don't want you to know.",
        f"If you're not using {words} yet, you're already falling behind.",
        f"This one {words} trick will save you hours every single week.",
        f"{words} is the future — and the future is already here.",
        f"Most people get {words} completely wrong. Here's what actually works.",
        f"Follow for more {words} insights and share this with someone who needs it!",
        f"Drop a 🔥 in the comments if {words} blew your mind today.",
        f"Like and subscribe — more {words} breakthroughs coming every day!",
    ]
    # Cycle through templates to fill num_scenes
    result = []
    for i in range(num_scenes):
        result.append(templates[i % len(templates)])
    return result


async def _generate_script(topic, num_scenes):
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
        # LLM unavailable — use offline template script
        return _offline_script(topic, num_scenes)



class AutoVideoPipeline(PipelineRun):
    pipeline = "auto_video"
    publish_platforms = ("youtube-shorts", "tiktok")

    async def execute(self) -> tuple[str, dict]:
        topic = self.params.get("topic", "").strip()
        if not topic:
            raise ValueError("topic is required")
        num_scenes = max(1, min(10, int(self.params.get("num_scenes", 5))))
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg not found on PATH")

        slug = slugify(topic)
        out_dir = OUTPUTS / "auto_video" / slug
        out_dir.mkdir(parents=True, exist_ok=True)

        await self.set_stage("script", 5)
        await self.emit("writer", "act", f"Generating {num_scenes}-scene script for: {topic}")
        sentences = await _generate_script(topic, num_scenes)
        await self.emit("writer", "done", f"Script ready: {len(sentences)} scenes")

        await self.set_stage("visuals", 15)
        clip_paths: list[Path] = []
        total_duration = 0.0

        with tempfile.TemporaryDirectory(prefix="av_") as tmp:
            tmp_path = Path(tmp)

            for i, sentence in enumerate(sentences):
                pct = 15 + int((i / num_scenes) * 50)
                await self.set_stage("audio", pct)
                await self.emit("designer", "act", f"Scene {i+1}/{num_scenes}: image + TTS")

                img_path   = tmp_path / f"scene_{i:02d}.png"
                audio_path = tmp_path / f"scene_{i:02d}.mp3"
                clip_path  = out_dir / f"clip_{i:02d}.mp4"

                await _make_scene_image(sentence, i, num_scenes, img_path)
                if not img_path.exists():
                    raise RuntimeError(f"Image render failed for scene {i+1}")

                await _make_tts_audio(sentence, audio_path)
                if not audio_path.exists() or audio_path.stat().st_size == 0:
                    raise RuntimeError(f"TTS failed for scene {i+1}")

                dur = await _audio_duration(audio_path)
                dur = max(2.0, dur + 0.5)
                total_duration += dur

                ok = await _make_clip(img_path, audio_path, clip_path, dur)
                if not ok:
                    raise RuntimeError(f"ffmpeg clip failed for scene {i+1}")

                clip_paths.append(clip_path)
                await self.emit("designer", "done",
                                f"Scene {i+1} clip: {clip_path.stat().st_size // 1024}KB")

            await self.set_stage("assembly", 70)
            await self.emit("publisher", "act", f"Concatenating {len(clip_paths)} clips")

            # Build concat list using safe Windows paths with forward slashes
            concat_file = tmp_path / "concat.txt"
            lines_txt = []
            for p in clip_paths:
                safe_p = str(p).replace("\\", "/")
                lines_txt.append("file '" + safe_p + "'\n")
            concat_file.write_text("".join(lines_txt), encoding="utf-8")

            concat_out = out_dir / "concat_raw.mp4"
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

            await self.set_stage("assembly", 85)
            await self.emit("publisher", "act", "Adding background music")

            bgm_path = tmp_path / "bgm.aac"
            has_bgm = await _generate_bgm(bgm_path, total_duration + 2)
            final_out = out_dir / "video.mp4"

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

        if not final_out.exists() or final_out.stat().st_size < 100_000:
            size = final_out.stat().st_size if final_out.exists() else 0
            raise RuntimeError(f"Final video too small or missing: {size} bytes (need >100KB)")

        final_size = final_out.stat().st_size
        await self.set_stage("assembly", 100)
        await self.emit("publisher", "done", f"Video ready: {final_size // 1024}KB")
        self.track_asset("video", str(final_out), caption=topic, tags=["auto_video", slug])

        return str(final_out), {
            "clips": len(clip_paths),
            "topic": topic,
            "num_scenes": num_scenes,
            "duration_s": round(total_duration, 1),
            "size_bytes": final_size,
        }


async def run(params: dict) -> dict:
    res = await AutoVideoPipeline(params).run()
    return res.__dict__
