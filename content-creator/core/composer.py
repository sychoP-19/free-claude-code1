"""composer.py -- Declarative video composition engine.
Inspired by Remotion composition model, implemented in pure Python + ffmpeg.
Build a VideoComposition from Clip objects, then call render() to assemble.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


def _escape_drawtext(s: str) -> str:
    """Escape text for ffmpeg drawtext filter value (backslash, colon, single-quote)."""
    s = s.replace(chr(92), chr(92) * 2)
    s = s.replace(chr(58), chr(92) + chr(58))
    s = s.replace(chr(39), chr(39) + chr(92) * 2 + chr(39) + chr(39))
    return s


async def _run_ffmpeg(*args: str) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode(errors="replace"), stderr.decode(errors="replace")


def _assert_nonzero(path: Path, label: str, min_bytes: int = 1000) -> None:
    if not path.exists():
        raise RuntimeError(f"{label}: output file missing: {path}")
    size = path.stat().st_size
    if size < min_bytes:
        raise RuntimeError(f"{label}: file too small ({size} bytes): {path}")


async def _probe_duration(path: Path) -> float:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    try:
        data = json.loads(stdout.decode())
        return float(data.get("format", {}).get("duration", 0))
    except Exception:
        return 0.0


@dataclass
class Clip:
    image_path: str | None = None
    video_path: str | None = None
    audio_path: str | None = None
    duration: float = 5.0
    text: str | None = None
    text_position: str = "bottom"
    text_size: int = 32
    text_color: str = "white"
    transition: str = "fade"
    transition_duration: float = 0.5


@dataclass
class VideoComposition:
    clips: list[Clip]
    width: int = 1920
    height: int = 1080
    fps: int = 30
    output_path: str = ""
    bgm_path: str | None = None
    bgm_volume: float = 0.12

    async def render(self) -> dict:
        """Render composition to video. Returns {ok, output_path, duration, error}."""
        if not self.clips:
            return {"ok": False, "output_path": "", "duration": 0.0, "error": "no clips"}
        if not shutil.which("ffmpeg"):
            return {"ok": False, "output_path": "", "duration": 0.0, "error": "ffmpeg not found"}
        tmp = Path(tempfile.mkdtemp(prefix="composer_"))
        try:
            return await self._render_impl(tmp)
        except Exception as e:
            return {"ok": False, "output_path": "", "duration": 0.0, "error": f"{type(e).__name__}: {e}"}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    async def _render_impl(self, tmp: Path) -> dict:
        w, h, fps = self.width, self.height, self.fps
        clip_paths: list[Path] = []
        for idx, clip in enumerate(self.clips):
            cv = await self._make_clip_video(clip, idx, tmp, w, h, fps)
            if clip.text:
                cv = await self._apply_text(clip, cv, idx, tmp)
            clip_paths.append(cv)
        assembled = (
            clip_paths[0] if len(clip_paths) == 1
            else await self._concat_clips(clip_paths, tmp)
        )
        final = Path(self.output_path) if self.output_path else tmp / "final.mp4"
        if self.output_path:
            Path(self.output_path).parent.mkdir(parents=True, exist_ok=True)
        if self.bgm_path and Path(self.bgm_path).exists():
            await self._mix_bgm(assembled, Path(self.bgm_path), final)
        else:
            shutil.copy2(assembled, final)
        _assert_nonzero(final, "final video", min_bytes=10_000)
        duration = await _probe_duration(final)
        return {"ok": True, "output_path": str(final), "duration": duration, "error": ""}

    async def _make_clip_video(
        self, clip: "Clip", idx: int, tmp: Path, w: int, h: int, fps: int
    ) -> Path:
        out = tmp / f"clip_{idx:03d}_raw.mp4"
        if clip.video_path and Path(clip.video_path).exists():
            vf = (
                f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
            )
            rc, _, err = await _run_ffmpeg(
                "-i", clip.video_path,
                "-vf", vf,
                "-r", str(fps), "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-an",
                str(out),
            )
            if rc != 0:
                raise RuntimeError(f"clip {idx} video scale failed: {err[-300:]}")
        elif clip.image_path and Path(clip.image_path).exists():
            dur = clip.duration
            if clip.audio_path and Path(clip.audio_path).exists():
                dur = await _probe_duration(Path(clip.audio_path))
            dur = max(1.0, dur)
            vf = (
                f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black"
            )
            rc, _, err = await _run_ffmpeg(
                "-loop", "1", "-i", clip.image_path, "-t", str(dur),
                "-vf", vf,
                "-r", str(fps), "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-an", "-pix_fmt", "yuv420p",
                str(out),
            )
            if rc != 0:
                raise RuntimeError(f"clip {idx} image-to-video failed: {err[-300:]}")
        else:
            raise RuntimeError(f"clip {idx} has no valid image_path or video_path")
        _assert_nonzero(out, f"clip {idx} raw video")
        if clip.audio_path and Path(clip.audio_path).exists():
            out_a = tmp / f"clip_{idx:03d}_audio.mp4"
            rc, _, err = await _run_ffmpeg(
                "-i", str(out), "-i", clip.audio_path,
                "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest",
                str(out_a),
            )
            if rc != 0:
                raise RuntimeError(f"clip {idx} audio mux failed: {err[-300:]}")
            _assert_nonzero(out_a, f"clip {idx} audio video")
            return out_a
        return out

    async def _apply_text(
        self, clip: "Clip", clip_video: Path, idx: int, tmp: Path
    ) -> Path:
        out = tmp / f"clip_{idx:03d}_text.mp4"
        escaped = _escape_drawtext(clip.text or "")
        pos_map = {
            "top":    "x=(w-text_w)/2:y=40",
            "center": "x=(w-text_w)/2:y=(h-text_h)/2",
            "bottom": "x=(w-text_w)/2:y=h-text_h-40",
        }
        pos = pos_map.get(clip.text_position, pos_map["bottom"])
        sq = chr(39)
        drawtext = (
            f"drawtext=text={sq}{escaped}{sq}"
            f":fontcolor={clip.text_color}"
            f":fontsize={clip.text_size}"
            f":box=1:boxcolor=black@0.5:boxborderw=8"
            f":{pos}"
        )
        rc, _, _ = await _run_ffmpeg(
            "-i", str(clip_video), "-vf", drawtext,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "copy",
            str(out),
        )
        if rc != 0 or not out.exists():
            return clip_video
        _assert_nonzero(out, f"clip {idx} text overlay")
        return out

    async def _concat_clips(self, clip_paths: list[Path], tmp: Path) -> Path:
        sq = chr(39)
        list_file = tmp / "concat.txt"
        list_file.write_text(
            "".join(f"file {sq}{p}{sq}\n" for p in clip_paths), encoding="utf-8"
        )
        out = tmp / "assembled.mp4"
        rc, _, err = await _run_ffmpeg(
            "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
            str(out),
        )
        if rc != 0:
            raise RuntimeError(f"concat failed: {err[-400:]}")
        _assert_nonzero(out, "assembled video", min_bytes=10_000)
        return out

    async def _mix_bgm(self, video: Path, bgm: Path, out: Path) -> None:
        vol = self.bgm_volume
        fc = (
            f"[0:a]aformat=sample_rates=44100:channel_layouts=stereo[va];"
            f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,volume={vol}[bgm];"
            f"[va][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
        rc, _, _ = await _run_ffmpeg(
            "-i", str(video), "-stream_loop", "-1", "-i", str(bgm),
            "-filter_complex", fc,
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart",
            str(out),
        )
        if rc != 0:
            shutil.copy2(video, out)


async def generate_thumbnail(output_video: str, timestamp: float = 2.0) -> str:
    """Extract a frame as PNG thumbnail. Returns thumbnail path or empty string."""
    src = Path(output_video)
    if not src.exists():
        return ""
    thumb = src.with_suffix(".png")
    duration = await _probe_duration(src)
    ts = min(timestamp, max(0.1, duration - 0.5)) if duration > 0.5 else 0.5
    rc, _, _ = await _run_ffmpeg(
        "-ss", str(ts), "-i", str(src),
        "-vframes", "1", "-q:v", "2",
        str(thumb),
    )
    if rc == 0 and thumb.exists() and thumb.stat().st_size > 0:
        return str(thumb)
    return ""
