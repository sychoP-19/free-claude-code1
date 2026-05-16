"""Layer 2b — Visual Asset Skill.

Builds PPTX slides, PDF storyboards, and image overlays
that the avatar presents over.
"""

from __future__ import annotations

import json
from pathlib import Path


class VisualAssetSkill:
    def __init__(self, config: dict):
        self.config = config
        self.assets_dir = Path(config["storage"]["assets_dir"])

    def build(self, script_result: dict, request) -> dict:
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        assets = {"ok": True, "slides": [], "storyboard": None, "overlays": []}

        # Build PPTX if skill available
        try:
            from skills.pptx_writer import build_slide_deck
            pptx_path = self.assets_dir / f"{request.topic[:40].replace(' ', '_')}_slides.pptx"
            segments = script_result.get("segments", [])
            build_slide_deck(
                segments=segments,
                output_path=str(pptx_path),
                title=script_result.get("title", request.topic),
                brand_logo=self.config["enhancement"]["branding"]["logo"],
            )
            assets["slides"].append(str(pptx_path))
        except ImportError:
            pass

        # Build PDF storyboard if skill available
        try:
            from skills.pdf_writer import build_storyboard
            pdf_path = self.assets_dir / f"{request.topic[:40].replace(' ', '_')}_storyboard.pdf"
            build_storyboard(
                segments=script_result.get("segments", []),
                shot_list=script_result.get("shot_list", []),
                output_path=str(pdf_path),
                title=script_result.get("title", request.topic),
            )
            assets["storyboard"] = str(pdf_path)
        except ImportError:
            pass

        return assets
