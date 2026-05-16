"""Layer 5 — Enhancement Pipeline.

Post-generation passes: background removal/replacement, auto-captioning,
logo/watermark branding, background music mixing, upscaling/denoising.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


class EnhancementPipeline:
    def __init__(self, config: dict):
        self.config = config
        self.temp_dir = Path(config["storage"]["temp_dir"])

    def run(self, avatar_result: dict, request) -> dict:
        if not avatar_result.get("ok"):
            return avatar_result

        video_path = avatar_result["video_path"]
        current = video_path

        # 1. Background removal / replacement
        bg_cfg = self.config["enhancement"]["background"]
        if bg_cfg["remove"]:
            current = self._remove_background(current)
            if bg_cfg["replace"]:
                current = self._replace_background(current, bg_cfg["replace"])

        # 2. Auto-captioning
        cap_cfg = self.config["enhancement"]["captions"]
        if cap_cfg["enabled"]:
            current = self._add_captions(current, cap_cfg)

        # 3. Branding overlay (logo / watermark)
        brand_cfg = self.config["enhancement"]["branding"]
        if brand_cfg["logo"] or brand_cfg["watermark_text"]:
            current = self._add_branding(current, brand_cfg)

        # 4. Background music
        music_cfg = self.config["enhancement"]["music"]
        if music_cfg["enabled"] and music_cfg["file"]:
            current = self._mix_music(current, music_cfg)

        # 5. Quality: upscale / denoise
        qual_cfg = self.config["enhancement"]["quality"]
        if qual_cfg["upscale"]:
            current = self._upscale(current, qual_cfg)
        elif qual_cfg["denoise"]:
            current = self._denoise(current)

        return {"ok": True, "video_path": current}

    def _remove_background(self, video_path: str) -> str:
        try:
            from rembg import remove
            # Frame-by-frame background removal for video
            out = str(self.temp_dir / "nobg_video.mp4")
            # Extract frames → rembg → reassemble
            # Simplified: use FFmpeg + rembg pipeline
            frames_dir = self.temp_dir / "frames_nb"
            frames_dir.mkdir(exist_ok=True)
            subprocess.run(["ffmpeg", "-y", "-i", video_path, f"{frames_dir}/frame_%04d.png"], capture_output=True, check=True)

            for img in sorted(frames_dir.glob("*.png")):
                from PIL import Image
                import io
                input_img = Image.open(img)
                output_img = remove(input_img)
                output_img.save(img)

            subprocess.run([
                "ffmpeg", "-y",
                "-framerate", "25",
                "-i", f"{frames_dir}/frame_%04d.png",
                "-i", video_path,  # Keep original audio
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "copy",
                out,
            ], capture_output=True, check=True)
            return out
        except Exception:
            return video_path

    def _replace_background(self, video_path: str, bg_path: str) -> str:
        # Use FFmpeg overlay to composite avatar over new background
        out = str(self.temp_dir / "bgreplaced_video.mp4")
        try:
            subprocess.run([
                "ffmpeg", "-y",
                "-i", bg_path, "-i", video_path,
                "-filter_complex", "[1:v]scale=1920:1080[fg];[0:v][fg]overlay=0:0",
                "-c:a", "copy", out,
            ], capture_output=True, check=True)
            return out
        except Exception:
            return video_path

    def _add_captions(self, video_path: str, cfg: dict) -> str:
        try:
            from whisper import Whisper
            model = Whisper("base")
            result = model.transcribe(video_path)
            srt_path = self.temp_dir / "captions.srt"
            self._write_srt(result["segments"], str(srt_path))
            out = str(self.temp_dir / "captioned_video.mp4")
            style = cfg.get("style", "default")
            force_style = f"FontSize={cfg.get('font_size', 24)},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000"
            subprocess.run([
                "ffmpeg", "-y", "-i", video_path,
                "-vf", f"subtitles={str(srt_path)}:force_style='{force_style}'",
                "-c:a", "copy", out,
            ], capture_output=True, check=True)
            return out
        except Exception:
            # Fallback: try faster-whisper
            try:
                from faster_whisper import WhisperModel
                model = WhisperModel("base", device="cpu", compute_type="int8")
                segments, _ = model.transcribe(video_path)
                srt_entries = []
                for i, seg in enumerate(segments, 1):
                    start = self._fmt_srt_time(seg.start)
                    end = self._fmt_srt_time(seg.end)
                    srt_entries.append(f"{i}\n{start} --> {end}\n{seg.text}\n")
                srt_path = self.temp_dir / "captions.srt"
                srt_path.write_text("\n".join(srt_entries))
                out = str(self.temp_dir / "captioned_video.mp4")
                subprocess.run([
                    "ffmpeg", "-y", "-i", video_path,
                    "-vf", f"subtitles={str(srt_path)}",
                    "-c:a", "copy", out,
                ], capture_output=True, check=True)
                return out
            except Exception:
                return video_path

    def _add_branding(self, video_path: str, cfg: dict) -> str:
        out = str(self.temp_dir / "branded_video.mp4")
        filters = []
        if cfg.get("logo") and Path(cfg["logo"]).exists():
            # Overlay logo in corner
            pos = cfg.get("position", "bottom-right")
            pos_map = {"bottom-right": "W-w-20:H-h-20", "bottom-left": "20:H-h-20", "top-right": "W-w-20:20", "top-left": "20:20"}
            overlay_pos = pos_map.get(pos, "W-w-20:H-h-20")
            filters.append(f"movie={cfg['logo']}[logo];[in][logo]overlay={overlay_pos}[out]")
        if cfg.get("watermark_text"):
            opacity = hex(int(cfg.get("watermark_opacity", 0.3) * 255))[2:].zfill(2)
            text = cfg["watermark_text"]
            filters.append(f"drawtext=text='{text}':fontcolor=white@{opacity}:fontsize=18:x=W-tw-20:y=H-th-20")

        if not filters:
            return video_path

        vf = ",".join(filters)
        try:
            subprocess.run(["ffmpeg", "-y", "-i", video_path, "-vf", vf, "-c:a", "copy", out], capture_output=True, check=True)
            return out
        except Exception:
            return video_path

    def _mix_music(self, video_path: str, cfg: dict) -> str:
        out = str(self.temp_dir / "music_video.mp4")
        volume = cfg.get("volume", 0.15)
        fade_in = cfg.get("fade_in", 1.0)
        fade_out = cfg.get("fade_out", 2.0)
        try:
            subprocess.run([
                "ffmpeg", "-y",
                "-i", video_path, "-i", cfg["file"],
                "-filter_complex",
                f"[1:a]volume={volume},afade=t=in:st=0:d={fade_in},afade=t=out:st=60:d={fade_out}[bg];[0:a][bg]amix=inputs=2:duration=first[aout]",
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac",
                out,
            ], capture_output=True, check=True)
            return out
        except Exception:
            return video_path

    def _upscale(self, video_path: str, cfg: dict) -> str:
        out = str(self.temp_dir / "upscaled_video.mp4")
        engine = cfg.get("upscale_engine", "realesrgan")
        try:
            if engine == "realesrgan":
                subprocess.run([
                    "realesrgan-ncnn-vulkan",
                    "-i", video_path, "-o", out,
                    "-s", "4", "-n", "realesrgan-x4plus",
                ], capture_output=True, check=True, timeout=600)
            elif engine == "gfpgan":
                subprocess.run([
                    "python", "-m", "gfpgan.inference_gfpgan",
                    "-i", video_path, "-o", str(self.temp_dir), "-v", "1.3",
                ], capture_output=True, check=True, timeout=600)
            if Path(out).exists():
                return out
        except Exception:
            pass
        return video_path

    def _denoise(self, video_path: str) -> str:
        out = str(self.temp_dir / "denoised_video.mp4")
        try:
            subprocess.run([
                "ffmpeg", "-y", "-i", video_path,
                "-vf", "hqdn3d=4:3:6:4.5",
                "-c:a", "copy", out,
            ], capture_output=True, check=True)
            return out
        except Exception:
            return video_path

    def _write_srt(self, segments: list, path: str):
        lines = []
        for i, seg in enumerate(segments, 1):
            start = self._fmt_srt_time(seg["start"])
            end = self._fmt_srt_time(seg["end"])
            lines.append(f"{i}\n{start} --> {end}\n{seg['text']}\n")
        Path(path).write_text("\n".join(lines))

    @staticmethod
    def _fmt_srt_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
