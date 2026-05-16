"""Layer 6 — Review & Iterate Loop.

Renders preview, lets user compare variants (A/B),
give feedback on specific segments, and re-run only the changed segment.
"""

from __future__ import annotations

import json
from pathlib import Path


class ReviewLoop:
    def __init__(self, config: dict):
        self.config = config
        self.temp_dir = Path(config["storage"]["temp_dir"])

    def present(self, enhanced_result: dict, request) -> dict:
        if not enhanced_result.get("ok"):
            return {"needs_rerun": False, "approved": False}

        video_path = enhanced_result["video_path"]

        # In CLI mode: auto-approve and skip interactive review
        # In UI mode: serve preview on localhost for A/B comparison
        return {
            "needs_rerun": False,
            "approved": True,
            "video_path": video_path,
            "preview_url": None,  # Set by UI layer when serving
        }

    def present_interactive(self, enhanced_result: dict, request) -> dict:
        """Interactive review — used by Gradio UI."""
        video_path = enhanced_result["video_path"]

        # Generate low-quality preview
        preview_path = self._generate_preview(video_path)

        return {
            "needs_rerun": False,
            "approved": True,
            "video_path": video_path,
            "preview_path": str(preview_path),
        }

    def process_feedback(self, feedback: dict) -> dict:
        """Process user feedback from the review UI.

        feedback format:
        {
          "action": "approve" | "rerun" | "ab_compare",
          "rerun_segments": ["script", "avatar"],  # which layers to re-run
          "notes": "Make the tone more casual",
          "variant": "A" | "B",  # for A/B comparison
        }
        """
        action = feedback.get("action", "approve")
        if action == "approve":
            return {"needs_rerun": False, "approved": True}
        elif action == "rerun":
            return {
                "needs_rerun": True,
                "approved": False,
                "rerun_segments": feedback.get("rerun_segments", []),
                "notes": feedback.get("notes", ""),
            }
        return {"needs_rerun": False, "approved": True}

    def _generate_preview(self, video_path: str) -> Path:
        import subprocess
        quality = self.config["review"]["preview_quality"]
        crf = {"low": 35, "medium": 28, "high": 23}.get(quality, 28)
        preview_path = self.temp_dir / "preview.mp4"
        try:
            subprocess.run([
                "ffmpeg", "-y", "-i", video_path,
                "-vcodec", "libx264", "-crf", str(crf),
                "-preset", "ultrafast",
                "-movflags", "+faststart",
                str(preview_path),
            ], capture_output=True, check=True, timeout=120)
        except Exception:
            # Fallback: just copy
            import shutil
            shutil.copy2(video_path, preview_path)
        return preview_path
