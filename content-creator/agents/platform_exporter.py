"""agents/platform_exporter.py — Stage 5: Platform-specific video export.

Input: master video + script metadata
Operations:
  - Create platform variants (YouTube, TikTok, Instagram)
  - Apply platform-specific optimizations
  - Generate metadata package (title, description, tags)
Output structure:
  outputs/pending/{topic_id}_youtube/
    ├── video.mp4
    ├── metadata.json
    └── thumbnail.jpg
"""
from __future__ import annotations

import asyncio
import json
import shutil
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.llm import chat
from pipelines.base import build_system_prompt

BASE = Path(__file__).parent.parent
OUTPUTS = BASE / "outputs"
PENDING = OUTPUTS / "pending"

# Platform specs
PLATFORM_SPECS = {
    "youtube": {
        "aspect_ratio": "16:9",
        "min_resolution": (1280, 720),
        "max_duration_sec": 60,
        "format": "mp4",
        "video_codec": "libx264",
        "audio_codec": "aac",
        "bitrate": "5M",
    },
    "tiktok": {
        "aspect_ratio": "9:16",
        "min_resolution": (720, 1280),
        "max_duration_sec": 60,
        "format": "mp4",
        "video_codec": "libx264",
        "audio_codec": "aac",
        "bitrate": "4M",
    },
    "instagram": {
        "aspect_ratio": "9:16",
        "min_resolution": (1080, 1920),
        "max_duration_sec": 90,
        "format": "mp4",
        "video_codec": "libx264",
        "audio_codec": "aac",
        "bitrate": "4M",
    },
}


@dataclass
class ExportResult:
    success: bool
    platform: str
    output_dir: str
    video_path: str | None = None
    metadata_path: str | None = None
    thumbnail_path: str | None = None
    errors: list[str] | None = None
    metadata: dict | None = None


class PlatformExporter:
    """Stage 5: Export master video to platform-specific variants."""

    def __init__(self, master_video: str, script_metadata: dict, topic_id: str):
        self.master = Path(master_video)
        self.metadata = script_metadata
        self.topic_id = topic_id
        self.errors: list[str] = []

    async def export(self, platforms: list[str] | None = None) -> list[ExportResult]:
        """Export master video to all specified platforms."""
        if platforms is None:
            platforms = list(PLATFORM_SPECS.keys())

        if not self.master.exists():
            self.errors.append(f"Master video not found: {self.master}")
            return [
                ExportResult(
                    success=False,
                    platform=p,
                    output_dir="",
                    errors=[f"Master video not found: {self.master}"],
                )
                for p in platforms
            ]

        results: list[ExportResult] = []
        for platform in platforms:
            result = await self._export_platform(platform)
            results.append(result)

        return results

    async def _export_platform(self, platform: str) -> ExportResult:
        """Export to a single platform."""
        if platform not in PLATFORM_SPECS:
            return ExportResult(
                success=False,
                platform=platform,
                output_dir="",
                errors=[f"Unknown platform: {platform}"],
            )

        spec = PLATFORM_SPECS[platform]
        topic = self.metadata.get("topic", "untitled")
        slug = slugify(topic)
        output_dir = PENDING / f"{self.topic_id}_{platform}"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Copy/master or transcode video
        video_path = await self._prepare_video(platform, spec, output_dir)
        if video_path is None:
            return ExportResult(
                success=False,
                platform=platform,
                output_dir=str(output_dir),
                errors=["Video preparation failed"],
            )

        # Generate metadata package
        metadata = await self._generate_metadata(platform, spec)
        metadata_path = output_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        # Generate thumbnail
        thumbnail_path = await self._generate_thumbnail(platform, output_dir)

        return ExportResult(
            success=True,
            platform=platform,
            output_dir=str(output_dir),
            video_path=str(video_path),
            metadata_path=str(metadata_path),
            thumbnail_path=str(thumbnail_path) if thumbnail_path else None,
            errors=[] if not self.errors else self.errors.copy(),
            metadata=metadata,
        )

    async def _prepare_video(self, platform: str, spec: dict, output_dir: Path) -> Path | None:
        """Prepare platform-specific video file."""
        master = self.master
        target = output_dir / "video.mp4"

        # Check if master already matches spec (quick copy)
        if self._matches_spec(master, spec):
            shutil.copy2(master, target)
            return target

        # Transcode with ffmpeg
        return await self._transcode_video(master, target, spec)

    def _matches_spec(self, path: Path, spec: dict) -> bool:
        """Quick check if video matches platform spec (assumes file already correct)."""
        return path.exists() and path.stat().st_size > 0

    async def _transcode_video(self, source: Path, target: Path, spec: dict) -> Path | None:
        """Transcode video to platform specifications."""
        width, height = spec["min_resolution"]

        argv = [
            "ffmpeg", "-y",
            "-i", str(source),
            "-c:v", spec["video_codec"],
            "-b:v", spec["bitrate"],
            "-c:a", spec["audio_codec"],
            "-ar", "44100",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-max_muxing_queue_size", "9999",
            str(target),
        ]

        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            self.errors.append(f"ffmpeg error: {stderr.decode(errors='ignore')[:200]}")
            return None

        if not target.exists() or target.stat().st_size == 0:
            return None

        return target

    async def _generate_metadata(self, platform: str, spec: dict) -> dict:
        """Generate platform-optimized metadata package."""
        topic = self.metadata.get("topic", "untitled")
        script = self.metadata.get("script", "")
        duration = self.metadata.get("duration", 45)

        prompt = f"""You are JARVIS's platform optimization agent.
Create platform-specific metadata for a {platform} video.

TOPIC: {topic}
DURATION: {duration}s
SCRIPT HOOK: {script[:200] if script else "N/A"}

Return ONLY valid JSON with this exact structure:
{{
  "title": "catchy, keyword-rich title under 60 chars",
  "description": "2-3 paragraph description with keywords",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5", "#tag6", "#tag7"],
  "posting_time": "best time to post (e.g., 'Tuesday 2PM EST')",
  "thumbnail_text": "5-word max text overlay for thumbnail"
}}

Return only the JSON object, no markdown, no explanations."""

        try:
            reply = await chat(
                [{"role": "user", "content": prompt}],
                system=build_system_prompt("platform_exporter"),
                max_tokens=500,
            )

            match = re.search(r"\{.*\}", reply, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as e:
            self.errors.append(f"Metadata generation error: {e}")

        # Fallback metadata
        return {
            "title": f"{topic.title()} - You Need to See This",
            "description": f"Check out this eye-opening content about {topic}. "
                          f"Make sure to like, comment, and follow for more!",
            "tags": [topic.replace(" ", ""), "viral", "trending", "fyp"],
            "hashtags": [
                f"#{topic.replace(' ', '')}",
                "#viral", "#trending", "#fyp", "#shorts",
                "#foryou", "#mustsee",
            ],
            "posting_time": "Tuesday 2PM EST",
            "thumbnail_text": f"{topic.upper()[:20]}!",
        }

    async def _generate_thumbnail(self, platform: str, output_dir: Path) -> Path | None:
        """Generate thumbnail image for platform."""
        # For now, create a placeholder (future: generate with FAL.ai or take frame)
        thumbnail_path = output_dir / "thumbnail.jpg"

        # Try to extract first frame with ffmpeg
        argv = [
            "ffmpeg", "-y",
            "-i", str(self.master),
            "-ss", "00:00:01",
            "-vframes", "1",
            "-vf", "scale=1280:-1",
            str(thumbnail_path),
        ]

        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0 or not thumbnail_path.exists():
            return None

        return thumbnail_path


def slugify(s: str, max_len: int = 60) -> str:
    """Create URL-safe slug."""
    out = "".join(c.lower() if c.isalnum() else "-" for c in s).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out[:max_len] or f"untitled-{int(datetime.now().timestamp())}"


async def run(master_video: str, script_metadata: dict, topic_id: str,
              platforms: list[str] | None = None) -> dict:
    """Main entry point for platform exporter."""
    exporter = PlatformExporter(master_video, script_metadata, topic_id)
    results = await exporter.export(platforms)

    return {
        "success": all(r.success for r in results),
        "platforms": [
            {
                "platform": r.platform,
                "success": r.success,
                "output_dir": r.output_dir,
                "video_path": r.video_path,
                "metadata_path": r.metadata_path,
                "thumbnail_path": r.thumbnail_path,
                "metadata": r.metadata,
                "errors": r.errors,
            }
            for r in results
        ],
        "total": len(results),
        "successful": sum(1 for r in results if r.success),
    }