"""Configuration loader."""

from pathlib import Path
import yaml


DEFAULT_CONFIG = {
    "llm": {"provider": "ollama", "model": "mistral:7b", "base_url": "http://localhost:11434", "temperature": 0.7, "max_tokens": 4096},
    "tts": {"engine": "xtts-v2", "language": "en", "voice_sample": None, "output_format": "wav"},
    "avatar": {"engine": "sadtalker", "cloud_provider": None, "cloud_api_key": None, "pose_style": 0, "still_mode": True},
    "lip_sync": {"engine": "wav2lip", "enhancer": "gfpgan"},
    "enhancement": {
        "background": {"remove": True, "replace": None, "engine": "rembg"},
        "captions": {"enabled": True, "engine": "faster-whisper", "style": "default", "font_size": 24, "position": "bottom"},
        "branding": {"logo": None, "watermark_text": None, "watermark_opacity": 0.3, "position": "bottom-right"},
        "music": {"enabled": False, "file": None, "volume": 0.15, "fade_in": 1.0, "fade_out": 2.0},
        "quality": {"upscale": False, "upscale_engine": "realesrgan", "denoise": True, "target_resolution": 1080},
    },
    "review": {"preview_quality": "medium", "serve_port": 7860, "auto_open": True},
    "output": {"format": "mp4", "codec": "libx264", "fps": 25, "resolution": "1920x1080", "output_dir": "./output"},
    "storage": {"db_path": "./data/avatar_agent.db", "models_dir": "./models", "assets_dir": "./assets", "temp_dir": "./temp"},
    "gpu": {"device": "auto", "memory_limit_gb": None},
}


def load_config(path: str = "config.yaml") -> dict:
    p = Path(path)
    if p.exists():
        with open(p) as f:
            user_cfg = yaml.safe_load(f) or {}
    else:
        user_cfg = {}

    return _deep_merge(DEFAULT_CONFIG, user_cfg)


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result
