"""pipelines/shorts.py — real YouTube shorts pipeline.

yt-dlp downloads the source, faster-whisper transcribes, Ollama scores the most
viral 45-60s windows, and ffmpeg crops them to portrait 1080x1920 with a
blurred-background letterbox.

Output: outputs/shorts/<source_id>/clip_<n>.mp4 (real bytes, typically multi-MB).
"""
from __future__ import annotations

import asyncio
import json
import re
import shutil
from pathlib import Path

from pipelines.base import PipelineRun, OUTPUTS, build_system_prompt
from pipelines.llm import chat

DOWNLOADS = OUTPUTS.parent / "downloads"


async def _run_tool(argv: list[str], timeout: float = 600) -> tuple[int, bytes, bytes]:
    """Safely launch an external binary by argv list (no shell interpolation)."""
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


class ShortsPipeline(PipelineRun):
    pipeline = "shorts"
    publish_platforms = ("youtube-shorts",)

    async def execute(self) -> tuple[str, dict]:
        url = self.params.get("youtube_url", "").strip()
        num_clips = int(self.params.get("num_clips", 3))
        if not url.startswith(("http://", "https://")):
            raise ValueError("youtube_url must be a full http(s) URL")
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg not found on PATH")
        if not shutil.which("yt-dlp"):
            raise RuntimeError("yt-dlp not found on PATH (install via: uv pip install yt-dlp)")

        await self.set_stage("research", 10)
        await self.emit("researcher", "act", f"Downloading {url}")
        source = await self._download(url)
        if not source.exists() or source.stat().st_size < 100_000:
            raise RuntimeError(f"yt-dlp produced empty file: {source}")

        await self.set_stage("script", 30)
        await self.emit("writer", "act", "Transcribing with faster-whisper")
        segments = await asyncio.to_thread(self._transcribe, source)
        if not segments:
            raise RuntimeError("transcription returned 0 segments")
        await self.emit("writer", "done", f"{len(segments)} segments transcribed")

        await self.set_stage("visuals", 55)
        await self.emit("strategist", "act", "Scoring viral windows with Ollama")
        windows = await self._score_windows(segments, num_clips)
        if not windows:
            duration = segments[-1]["end"]
            stride = max(60, duration / (num_clips + 1))
            windows = [{"start": i * stride, "end": min(i * stride + 55, duration), "reason": "stride-fallback"}
                       for i in range(1, num_clips + 1)]
        await self.emit("strategist", "done", f"{len(windows)} windows selected")

        await self.set_stage("assembly", 80)
        await self.emit("designer", "act", f"Cropping {len(windows)} clips with ffmpeg")
        clip_paths = await self._crop_all(source, windows)
        if not clip_paths:
            raise RuntimeError("ffmpeg produced no clips")

        await self.set_stage("assembly", 100)
        await self.emit("publisher", "done", f"{len(clip_paths)} clips ready")
        for i, p in enumerate(clip_paths):
            self.track_asset("video", p, caption=f"clip {i+1}", tags=["shorts", "youtube"])

        return clip_paths[0], {"clips": clip_paths, "source": str(source),
                               "windows": windows, "segments_count": len(segments)}

    async def _download(self, url: str) -> Path:
        DOWNLOADS.mkdir(parents=True, exist_ok=True)
        out_tpl = str(DOWNLOADS / "source_%(id)s.%(ext)s")
        argv = [
            "yt-dlp",
            "-f", "bv*[height<=720]+ba/b[height<=720]",
            "--merge-output-format", "mp4",
            "-o", out_tpl,
            "--no-playlist",
            "--print", "after_move:filepath",
            url,
        ]
        rc, stdout, stderr = await _run_tool(argv)
        if rc != 0:
            raise RuntimeError(f"yt-dlp failed: {stderr.decode(errors='ignore')[:300]}")
        last_line = stdout.decode(errors='ignore').strip().splitlines()
        if not last_line:
            raise RuntimeError("yt-dlp produced no output path")
        return Path(last_line[-1])

    def _transcribe(self, source: Path) -> list[dict]:
        from faster_whisper import WhisperModel
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(str(source), beam_size=1, vad_filter=True)
        return [{"start": float(s.start), "end": float(s.end), "text": s.text.strip()}
                for s in segments]

    async def _score_windows(self, segments: list[dict], n: int) -> list[dict]:
        candidates: list[dict] = []
        i = 0
        while i < len(segments):
            start = segments[i]["start"]
            j = i
            while j < len(segments) and segments[j]["end"] - start < 55:
                j += 1
            if j > i:
                end = segments[min(j, len(segments) - 1)]["end"]
                if end - start >= 30:
                    text = " ".join(segments[k]["text"] for k in range(i, j))
                    candidates.append({"start": start, "end": min(end, start + 60), "text": text[:600]})
            i += max(1, (j - i) // 2)
        if not candidates:
            return []
        prompt = (
            "Rate each candidate 60-second YouTube Shorts window by virality (1-10). "
            "Consider hook strength, emotional spike, narrative payoff, and quotability. "
            f"Return ONLY a JSON array of objects with keys: index, score, reason. "
            f"Pick exactly {n} winners.\n\n"
            + "\n".join(f"[{idx}] ({c['start']:.0f}s) {c['text']}" for idx, c in enumerate(candidates))
        )
        try:
            reply = await chat(
                [{"role": "user", "content": prompt}],
                system=build_system_prompt("strategist"),
                max_tokens=600, run_id=self.run_id,
            )
            m = re.search(r"\[.*\]", reply, re.DOTALL)
            if not m:
                return []
            arr = json.loads(m.group())
            winners = sorted(arr, key=lambda x: -float(x.get("score", 0)))[:n]
            return [
                {"start": candidates[w["index"]]["start"],
                 "end":   candidates[w["index"]]["end"],
                 "score": w.get("score"), "reason": w.get("reason", "")}
                for w in winners if 0 <= int(w.get("index", -1)) < len(candidates)
            ]
        except Exception:
            return []

    async def _crop_all(self, source: Path, windows: list[dict]) -> list[str]:
        out_dir = OUTPUTS / "shorts" / source.stem
        out_dir.mkdir(parents=True, exist_ok=True)
        paths: list[str] = []
        vf = (
            "[0:v]split=2[bg][fg];"
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,gblur=sigma=20[bgb];"
            "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fgs];"
            "[bgb][fgs]overlay=(W-w)/2:(H-h)/2"
        )
        for i, w in enumerate(windows):
            out = out_dir / f"clip_{i+1:02d}.mp4"
            start = float(w["start"])
            dur = max(15.0, float(w["end"]) - start)
            argv = [
                "ffmpeg", "-y",
                "-ss", f"{start:.2f}", "-t", f"{dur:.2f}",
                "-i", str(source),
                "-filter_complex", vf,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                str(out),
            ]
            rc, _, stderr = await _run_tool(argv, timeout=300)
            if rc == 0 and out.exists() and out.stat().st_size > 50_000:
                paths.append(str(out))
            else:
                await self.emit("designer", "error",
                                f"clip {i+1} failed: {stderr.decode(errors='ignore')[:160]}")
        return paths


async def run(params: dict) -> dict:
    res = await ShortsPipeline(params).run()
    return res.__dict__
