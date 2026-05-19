"""Stage 4: Video Assembly Agent.

Takes scene images from Stage 3 and assembles them into a final video:
- Converts scene images to 3-second video clips
- Generates TTS audio via gTTS
- Assembles final MP4 using moviepy/ffmpeg

Output: outputs/videos/{topic_id}_master.mp4
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Constants
VIDEOS_BASE = Path(__file__).parent.parent / "outputs" / "videos"
DEFAULT_CLIP_DURATION = 3.0  # seconds per scene


@dataclass
class VideoAssemblyResult:
    """Result from video assembly."""
    ok: bool
    output_path: str
    video_bytes: int
    clips_created: int
    audio_path: str | None
    duration_s: float
    errors: list[str]
    elapsed_s: float


async def assemble_video(
    asset_paths: list[str],
    topic_id: str,
    script_text: str = "",
    clip_duration: float = DEFAULT_CLIP_DURATION,
    voice_lang: str = "en",
    voice_speed: float = 1.0,
) -> VideoAssemblyResult:
    """Assemble final video from assets.

    Args:
        asset_paths: List of paths to scene images/videos from Stage 3
        topic_id: Unique identifier for this topic
        script_text: Optional script text for TTS generation
        clip_duration: Duration in seconds for each scene clip
        voice_lang: Language code for TTS (default: "en")
        voice_speed: Speech synthesis speed (default: 1.0)

    Returns:
        VideoAssemblyResult with path to final video
    """
    started = time.time()
    videos_dir = VIDEOS_BASE
    videos_dir.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []

    # Filter valid asset paths
    valid_assets = [p for p in asset_paths if p and Path(p).exists()]

    if not valid_assets:
        return VideoAssemblyResult(
            ok=False,
            output_path="",
            video_bytes=0,
            clips_created=0,
            audio_path=None,
            duration_s=0,
            errors=["No valid asset paths provided"],
            elapsed_s=0,
        )

    # Step 1: Generate TTS audio if script provided
    audio_path: str | None = None

    if script_text.strip():
        audio_result = await _generate_tts(script_text, topic_id, voice_lang, voice_speed)
        if audio_result.get("ok"):
            audio_path = audio_result["path"]
            logger.info(f"TTS audio generated: {audio_path}")
        else:
            errors.append(f"TTS generation failed: {audio_result.get('error', 'unknown')}")
            logger.warning(f"TTS failed, proceeding without audio: {audio_result.get('error')}")

    # Step 2: Create video clips from assets
    clip_paths = await _create_clips(valid_assets, topic_id, clip_duration)

    if not clip_paths:
        return VideoAssemblyResult(
            ok=False,
            output_path="",
            video_bytes=0,
            clips_created=0,
            audio_path=audio_path,
            duration_s=0,
            errors=["Failed to create any video clips"],
            elapsed_s=round(time.time() - started, 1),
        )

    # Step 3: Assemble final video
    output_path, final_errors = await _assemble_final_video(
        clip_paths, topic_id, audio_path
    )

    errors.extend(final_errors)

    if not output_path:
        return VideoAssemblyResult(
            ok=False,
            output_path="",
            video_bytes=0,
            clips_created=len(clip_paths),
            audio_path=audio_path,
            duration_s=0,
            errors=errors or ["Video assembly failed"],
            elapsed_s=round(time.time() - started, 1),
        )

    elapsed = time.time() - started
    video_bytes = output_path.stat().st_size if output_path.exists() else 0

    logger.info(f"Video assembly complete: {output_path} ({video_bytes} bytes)")

    return VideoAssemblyResult(
        ok=True,
        output_path=str(output_path),
        video_bytes=video_bytes,
        clips_created=len(clip_paths),
        audio_path=audio_path,
        duration_s=round(len(clip_paths) * clip_duration, 1),
        errors=errors,
        elapsed_s=round(elapsed, 1),
    )


async def _generate_tts(
    script: str,
    topic_id: str,
    lang: str,
    speed: float,
) -> dict:
    """Generate TTS audio using gTTS.

    Args:
        script: Text script to convert to speech
        topic_id: Topic identifier for filename
        lang: Language code
        speed: Speech speed (1.0 = normal)

    Returns:
        {"ok": bool, "path": str, "error": str}
    """
    try:
        from gtts import gTTS
    except ImportError:
        return {"ok": False, "error": "gTTS not installed (run: uv pip install gTTS)"}

    output_path = VIDEOS_BASE / f"{topic_id}_narration.mp3"

    try:
        # Create TTS instance
        tts = gTTS(text=script.strip(), lang=lang, slow=False)

        # Save to file
        tts.save(str(output_path))

        # Validate output
        if not output_path.exists():
            return {"ok": False, "error": "gTTS failed to create output file"}

        size = output_path.stat().st_size
        if size < 1024:
            return {"ok": False, "error": f"gTTS produced invalid file ({size} bytes)"}

        return {"ok": True, "path": str(output_path), "bytes": size}

    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


async def _create_clips(
    asset_paths: list[str],
    topic_id: str,
    duration: float,
) -> list[str]:
    """Convert assets to video clips.

    Args:
        asset_paths: Paths to source images/videos
        topic_id: Topic identifier
        duration: Duration for each clip in seconds

    Returns:
        List of paths to created clips
    """
    clips_dir = VIDEOS_BASE / f"{topic_id}_clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    clip_paths: list[str] = []

    # Check if moviepy is available
    try:
        from moviepy.editor import ImageClip, VideoFileClip, concatenate_videoclips

        for idx, asset_path in enumerate(asset_paths):
            try:
                asset = Path(asset_path)
                if not asset.exists():
                    continue

                clip_output = clips_dir / f"clip_{idx:03d}.mp4"

                # Check if it's an image or video
                suffix = asset.suffix.lower()

                if suffix in [".jpg", ".jpeg", ".png", ".webp"]:
                    # Create video from image
                    clip = ImageClip(str(asset)).set_duration(duration)
                    clip.write_videofile(
                        str(clip_output),
                        fps=24,
                        codec="libx264",
                        audio=False,
                        logger=None,
                    )
                elif suffix in [".mp4", ".webm", ".mov"]:
                    # Use video asset as-is (trim if needed)
                    video = VideoFileClip(str(asset))
                    clip = video.subclip(0, min(duration, video.duration))
                    clip.write_videofile(
                        str(clip_output),
                        fps=24,
                        codec="libx264",
                        audio=False,
                        logger=None,
                    )
                    video.close()
                else:
                    logger.warning(f"Unknown asset type: {suffix}")
                    continue

                if clip_output.exists() and clip_output.stat().st_size > 1000:
                    clip_paths.append(str(clip_output))

            except Exception as e:
                logger.warning(f"Failed to create clip {idx}: {type(e).__name__}: {e}")
                continue

    except ImportError:
        # Fallback to ffmpeg directly
        logger.info("moviepy not available, using ffmpeg")
        clip_paths = await _create_clips_ffmpeg(asset_paths, topic_id, clips_dir, duration)

    return clip_paths


async def _create_clips_ffmpeg(
    asset_paths: list[str],
    topic_id: str,
    clips_dir: Path,
    duration: float,
) -> list[str]:
    """Create clips using ffmpeg directly (fallback when moviepy unavailable)."""
    clip_paths: list[str] = []

    for idx, asset_path in enumerate(asset_paths):
        asset = Path(asset_path)
        if not asset.exists():
            continue

        clip_output = clips_dir / f"clip_{idx:03d}.mp4"
        suffix = asset.suffix.lower()

        try:
            if suffix in [".jpg", ".jpeg", ".png", ".webp"]:
                # Create video from image using ffmpeg
                result = subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-loop", "1",
                        "-i", str(asset),
                        "-t", str(duration),
                        "-c:v", "libx264",
                        "-tune", "stillimage",
                        "-pix_fmt", "yuv420p",
                        str(clip_output),
                    ],
                    capture_output=True,
                    timeout=30,
                )

                if result.returncode == 0 and clip_output.exists():
                    clip_paths.append(str(clip_output))

            elif suffix in [".mp4", ".webm", ".mov"]:
                # Trim video
                result = subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i", str(asset),
                        "-t", str(duration),
                        "-c", "copy",
                        str(clip_output),
                    ],
                    capture_output=True,
                    timeout=30,
                )

                if result.returncode == 0 and clip_output.exists():
                    clip_paths.append(str(clip_output))

        except FileNotFoundError:
            logger.error("ffmpeg not found")
            break
        except subprocess.TimeoutExpired:
            logger.warning(f"ffmpeg timeout for clip {idx}")
            continue
        except Exception as e:
            logger.warning(f"ffmpeg error for clip {idx}: {e}")
            continue

    return clip_paths


async def _assemble_final_video(
    clip_paths: list[str],
    topic_id: str,
    audio_path: str | None,
) -> tuple[Path | None, list[str]]:
    """Assemble final video from clips.

    Args:
        clip_paths: Paths to individual clip files
        topic_id: Topic identifier
        audio_path: Optional path to audio file

    Returns:
        (output_path, errors) tuple
    """
    errors: list[str] = []
    output_path = VIDEOS_BASE / f"{topic_id}_master.mp4"

    # Try moviepy first
    try:
        from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip

        clips = []
        try:
            for clip_path in clip_paths:
                clip = VideoFileClip(clip_path)
                clips.append(clip)

            if not clips:
                errors.append("No clips to assemble")
                return None, errors

            # Concatenate clips
            final = concatenate_videoclips(clips, method="compose")

            # Add audio if available
            if audio_path and Path(audio_path).exists():
                try:
                    audio = AudioFileClip(audio_path)
                    # Trim or loop audio to match video duration
                    audio_duration = min(final.duration, audio.duration)
                    audio = audio.subclip(0, audio_duration)
                    final = final.set_audio(audio)
                except Exception as e:
                    errors.append(f"Failed to add audio: {type(e).__name__}: {e}")

            # Write final video
            final.write_videofile(
                str(output_path),
                fps=24,
                codec="libx264",
                audio_codec="aac",
                logger=None,
            )

            # Clean up
            for clip in clips:
                clip.close()

        finally:
            # Ensure all clips are closed
            for clip in clips:
                try:
                    clip.close()
                except:
                    pass

    except ImportError:
        logger.info("moviepy not available, using ffmpeg")
        return await _assemble_ffmpeg(clip_paths, topic_id, audio_path, output_path)

    except Exception as e:
        errors.append(f"moviepy assembly failed: {type(e).__name__}: {e}")
        return await _assemble_ffmpeg(clip_paths, topic_id, audio_path, output_path)

    # Validate output
    if not output_path.exists():
        errors.append("Final video file not created")
        return None, errors

    size = output_path.stat().st_size
    if size < 10_000:
        errors.append(f"Final video too small ({size} bytes)")
        return None, errors

    return output_path, errors


async def _assemble_ffmpeg(
    clip_paths: list[str],
    topic_id: str,
    audio_path: str | None,
    output_path: Path,
) -> tuple[Path | None, list[str]]:
    """Assemble video using ffmpeg (fallback)."""
    errors: list[str] = []

    # Create concat file
    concat_file = VIDEOS_BASE / f"{topic_id}_concat.txt"

    try:
        with open(concat_file, "w") as f:
            for clip_path in clip_paths:
                f.write(f"file '{clip_path}'\n")

        # Build ffmpeg command
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
        ]

        if audio_path and Path(audio_path).exists():
            cmd.extend([
                "-i", audio_path,
                "-c:v", "libx264",
                "-c:a", "aac",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
            ])
        else:
            cmd.extend([
                "-c", "copy",
            ])

        cmd.append(str(output_path))

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=300,
        )

        if result.returncode != 0:
            errors.append(f"ffmpeg failed: {result.stderr.decode(errors='ignore')[:200]}")
            return None, errors

    except FileNotFoundError:
        errors.append("ffmpeg not found")
        return None, errors
    except subprocess.TimeoutExpired:
        errors.append("ffmpeg timeout during assembly")
        return None, errors
    except Exception as e:
        errors.append(f"Assembly failed: {type(e).__name__}: {e}")
        return None, errors
    finally:
        # Clean up concat file
        try:
            concat_file.unlink()
        except:
            pass

    return output_path, errors