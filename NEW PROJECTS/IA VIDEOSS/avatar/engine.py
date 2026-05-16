"""Layer 4 — Avatar Generation Engine.

Handles TTS, voice cloning, lip-sync, avatar rendering.
Supports local (SadTalker, MuseTalk) and cloud (HeyGen, D-ID, Synthesia).
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import httpx


class AvatarEngine:
    def __init__(self, config: dict):
        self.config = config
        self.temp_dir = Path(config["storage"]["temp_dir"])
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def render(self, script: dict, assets: dict, request) -> dict:
        segments = script.get("segments", [])
        segment_videos = []

        for seg in segments:
            text = seg.get("text", "")
            seg_id = seg.get("id", "seg")

            # Step 1: TTS
            audio_path = self._tts(text, request, seg_id)
            # If TTS is disabled, we'll use a silent audio file or skip audio
            if audio_path is None and self.config["tts"]["engine"] is not None:
                return {"ok": False, "error": f"TTS failed for segment {seg_id}"}

            # Step 2: Avatar render with lip-sync
            video_path = self._render_avatar(audio_path, request, seg_id)
            # If avatar rendering is disabled, we can still proceed
            if video_path is None and self.config["avatar"]["engine"] is not None:
                return {"ok": False, "error": f"Avatar render failed for segment {seg_id}"}

            segment_videos.append(video_path)

        # Step 3: Concatenate segments
        if len(segment_videos) > 1:
            final_path = self._concat_segments(segment_videos)
        else:
            final_path = segment_videos[0] if segment_videos and segment_videos[0] else None

        return {"ok": True, "video_path": str(final_path) if final_path else None, "segments": segment_videos}

    def _tts(self, text: str, request, seg_id: str) -> str | None:
        engine = self.config["tts"]["engine"]
        out_path = self.temp_dir / f"{seg_id}.wav"

        # If TTS is disabled, return None to skip TTS processing
        if engine is None or engine == "null" or engine == "":
            return None

        if engine == "xtts-v2":
            return self._tts_xtts(text, str(out_path), request)
        elif engine == "piper":
            return self._tts_piper(text, str(out_path))
        elif engine == "bark":
            return self._tts_bark(text, str(out_path))
        return None

    def _tts_xtts(self, text: str, out_path: str, request) -> str | None:
        try:
            from TTS.api import TTS
            tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
            speaker = self.config["tts"]["voice_sample"] or None
            tts.tts_to_file(text=text, file_path=out_path, language=request.language, speaker_wav=speaker)
            return out_path
        except Exception:
            return self._tts_ollama_fallback(text, out_path)

    def _tts_piper(self, text: str, out_path: str) -> str | None:
        try:
            subprocess.run(["piper", "--model", "en_US-lessac-medium", "--output_file", out_path], input=text, text=True, capture_output=True, check=True)
            return out_path
        except Exception:
            return None

    def _tts_bark(self, text: str, out_path: str) -> str | None:
        try:
            from bark import generate_audio, SAMPLE_RATE
            import scipy.io.wavfile as wavfile
            audio = generate_audio(text)
            wavfile.write(out_path, SAMPLE_RATE, audio)
            return out_path
        except Exception:
            return None

    def _tts_ollama_fallback(self, text: str, out_path: str) -> str | None:
        # Use Ollama's /api/tts if available, else skip
        try:
            resp = httpx.post(f"{self.config['llm']['base_url']}/api/tts", json={"model": self.config["llm"]["model"], "input": text}, timeout=60.0)
            if resp.status_code == 200:
                Path(out_path).write_bytes(resp.content)
                return out_path
        except Exception:
            pass
        return None

    def _render_avatar(self, audio_path: str, request, seg_id: str) -> str | None:
        engine = self.config["avatar"]["engine"]
        out_path = self.temp_dir / f"{seg_id}_avatar.mp4"

        # If no avatar engine is specified, return None
        if engine is None or engine == "null" or engine == "":
            # Create a simple video with the assets if available
            return None

        # If no audio is provided (TTS disabled), we can still generate avatar without lip-sync
        if audio_path is None:
            # Create a silent audio file for lip-sync
            silent_audio = self.temp_dir / f"{seg_id}_silent.wav"
            try:
                # Create a 1-second silent WAV file
                import wave
                import struct
                with wave.open(str(silent_audio), 'w') as f:
                    f.setnchannels(1)
                    f.setsampwidth(2)
                    f.setframerate(44100)
                    f.setnframes(44100)  # 1 second of silence
                    f.writeframes(struct.pack('<h', 0) * 44100)
            except Exception:
                pass
            audio_path = str(silent_audio)

        # Cloud provider fallback
        cloud = self.config["avatar"]["cloud_provider"]
        if cloud and self.config["avatar"]["cloud_api_key"]:
            return self._render_cloud(engine, audio_path, request, seg_id)

        if engine == "sadtalker":
            return self._render_sadtalker(audio_path, str(out_path))
        elif engine == "musetalk":
            return self._render_musetalk(audio_path, str(out_path))
        return None

    def _render_sadtalker(self, audio_path: str, out_path: str) -> str | None:
        try:
            # SadTalker expects: python inference.py --driven_audio <wav> --source_image <img> --result_dir <dir>
            # This assumes SadTalker is installed and on PATH
            source_image = self.config["avatar"].get("source_image", "assets/default_avatar.png")
            result_dir = str(Path(out_path).parent)
            cmd = [
                "python", "-m", "sadtalker.inference",
                "--driven_audio", audio_path,
                "--source_image", source_image,
                "--result_dir", result_dir,
                "--pose_style", str(self.config["avatar"]["pose_style"]),
                "--still" if self.config["avatar"]["still_mode"] else "--no-still",
                "--preprocess", "crop",
                "--enhancer", self.config["lip_sync"]["enhancer"] or "None",
            ]
            subprocess.run(cmd, capture_output=True, check=True, timeout=300)
            # SadTalker outputs to result_dir with date-stamped name
            mp4s = list(Path(result_dir).glob("*.mp4"))
            if mp4s:
                mp4s[-1].rename(out_path)
                return out_path
        except Exception:
            pass
        return None

    def _render_musetalk(self, audio_path: str, out_path: str) -> str | None:
        try:
            cmd = ["python", "-m", "musetalk", "--audio", audio_path, "--output", out_path]
            subprocess.run(cmd, capture_output=True, check=True, timeout=300)
            if Path(out_path).exists():
                return out_path
        except Exception:
            pass
        return None

    def _render_cloud(self, provider: str, audio_path: str, request, seg_id: str) -> str | None:
        api_key = self.config["avatar"]["cloud_api_key"]
        out_path = self.temp_dir / f"{seg_id}_cloud.mp4"

        if provider == "heygen":
            return self._heygen(api_key, request, seg_id, str(out_path))
        elif provider == "did":
            return self._did(api_key, audio_path, str(out_path))
        elif provider == "synthesia":
            return self._synthesia(api_key, request, str(out_path))
        return None

    def _heygen(self, api_key: str, request, seg_id: str, out_path: str) -> str | None:
        try:
            headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
            payload = {
                "video_inputs": [{
                    "character": {"type": "avatar", "avatar_id": request.avatar_id or "josh-lite3"},
                    "voice": {"type": "text", "input_text": request.prompt[:500]},
                }],
                "dimension": {"width": 1920, "height": 1080},
            }
            resp = httpx.post("https://api.heygen.com/v2/video/generate", json=payload, headers=headers, timeout=60.0)
            resp.raise_for_status()
            video_id = resp.json()["data"]["video_id"]
            # Poll for completion (simplified)
            import time
            for _ in range(60):
                status = httpx.get(f"https://api.heygen.com/v1/video_status.get?video_id={video_id}", headers=headers)
                data = status.json().get("data", {})
                if data.get("status") == "completed":
                    video_url = data["video_url"]
                    vid = httpx.get(video_url)
                    Path(out_path).write_bytes(vid.content)
                    return out_path
                time.sleep(5)
        except Exception:
            pass
        return None

    def _did(self, api_key: str, audio_path: str, out_path: str) -> str | None:
        try:
            headers = {"Authorization": f"Basic {api_key}", "Content-Type": "application/json"}
            audio_b64 = __import__("base64").b64encode(Path(audio_path).read_bytes()).decode()
            payload = {"script": {"type": "audio", "audio_url": f"data:audio/wav;base64,{audio_b64[:10000]}"}
                       , "source_url": "https://clips.d-id.com/alex/default.png"}
            resp = httpx.post("https://api.d-id.com/talks", json=payload, headers=headers, timeout=60.0)
            resp.raise_for_status()
            talk_id = resp.json()["id"]
            import time
            for _ in range(60):
                status = httpx.get(f"https://api.d-id.com/talks/{talk_id}", headers=headers)
                data = status.json()
                if data.get("result_url"):
                    vid = httpx.get(data["result_url"])
                    Path(out_path).write_bytes(vid.content)
                    return out_path
                time.sleep(5)
        except Exception:
            pass
        return None

    def _synthesia(self, api_key: str, request, out_path: str) -> str | None:
        # Synthesia API v2 — similar pattern
        return None

    def _concat_segments(self, video_paths: list[str]) -> str:
        out_path = self.temp_dir / "full_video.mp4"
        list_file = self.temp_dir / "concat_list.txt"
        with open(list_file, "w") as f:
            for vp in video_paths:
                f.write(f"file '{vp}'\n")
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out_path)]
        subprocess.run(cmd, capture_output=True, check=True, timeout=120)
        return str(out_path)
