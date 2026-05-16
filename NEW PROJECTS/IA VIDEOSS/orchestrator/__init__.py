"""Layer 1 — Orchestrator Agent.

Parses user intent, routes tasks, manages state between steps,
handles retry/error recovery. This is the brain of the system.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from config import load_config
from skills.script_content import ScriptContentSkill
from skills.visual_asset import VisualAssetSkill
from skills.file_reader import FileReaderSkill
from avatar.engine import AvatarEngine
from enhancement.pipeline import EnhancementPipeline
from review.loop import ReviewLoop
from output.delivery import OutputDelivery


class PipelineState(str, Enum):
    IDLE = "idle"
    PARSING = "parsing"
    SCRIPT_GEN = "script_gen"
    ASSET_BUILD = "asset_build"
    AVATAR_RENDER = "avatar_render"
    ENHANCEMENT = "enhancement"
    REVIEW = "review"
    OUTPUT = "output"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class VideoRequest:
    prompt: str
    topic: str = ""
    tone: str = "professional"
    language: str = "en"
    duration_seconds: int = 60
    avatar_id: Optional[str] = None
    voice_id: Optional[str] = None
    source_files: list[str] = field(default_factory=list)
    output_format: str = "mp4"


@dataclass
class PipelineResult:
    success: bool
    output_path: Optional[str] = None
    error: Optional[str] = None
    segments: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


class Orchestrator:
    def __init__(self, config: dict):
        self.config = config
        self.state = PipelineState.IDLE
        self.script_skill = ScriptContentSkill(config)
        self.visual_skill = VisualAssetSkill(config)
        self.file_skill = FileReaderSkill(config)
        self.avatar_engine = AvatarEngine(config)
        self.enhancement = EnhancementPipeline(config)
        self.review = ReviewLoop(config)
        self.delivery = OutputDelivery(config)
        self._setup_dirs()

    def _setup_dirs(self):
        for key in ("db_path", "models_dir", "assets_dir", "temp_dir"):
            p = Path(self.config["storage"][key])
            p.parent.mkdir(parents=True, exist_ok=True)
        Path(self.config["output"]["output_dir"]).mkdir(parents=True, exist_ok=True)

    def run(self, prompt: str, **overrides) -> PipelineResult:
        request = self._parse_intent(prompt, **overrides)
        segment_states = {}

        try:
            # ---- Layer 2a: Script & Content ----
            self.state = PipelineState.SCRIPT_GEN
            script_result = self.script_skill.generate(request)
            segment_states["script"] = script_result
            if not script_result.get("ok"):
                return PipelineResult(success=False, error=script_result.get("error", "Script generation failed"))

            # ---- Layer 3: Source file reading (on-demand) ----
            if request.source_files:
                file_context = self.file_skill.read(request.source_files)
                if file_context.get("extra_context"):
                    script_result["context"] = file_context["extra_context"]

            # ---- Layer 2b: Visual Assets ----
            self.state = PipelineState.ASSET_BUILD
            asset_result = self.visual_skill.build(script_result, request)
            segment_states["visual"] = asset_result
            if not asset_result.get("ok"):
                return PipelineResult(success=False, error=asset_result.get("error", "Visual asset build failed"))

            # ---- Layer 4: Avatar Generation Engine ----
            self.state = PipelineState.AVATAR_RENDER
            avatar_result = self.avatar_engine.render(
                script=script_result,
                assets=asset_result,
                request=request,
            )
            segment_states["avatar"] = avatar_result
            if not avatar_result.get("ok"):
                return PipelineResult(success=False, error=avatar_result.get("error", "Avatar rendering failed"))

            # ---- Layer 5: Enhancement Pipeline ----
            self.state = PipelineState.ENHANCEMENT
            enhanced_result = self.enhancement.run(avatar_result, request)
            segment_states["enhanced"] = enhanced_result

            # ---- Layer 6: Review & Iterate ----
            self.state = PipelineState.REVIEW
            review_result = self.review.present(enhanced_result, request)
            segment_states["review"] = review_result

            if review_result.get("needs_rerun"):
                # Re-run only the affected segment(s), not the whole video
                for segment_key in review_result.get("rerun_segments", []):
                    rerun_result = self._rerun_segment(segment_key, segment_states, request)
                    segment_states[segment_key] = rerun_result

            # ---- Layer 7: Output Delivery ----
            self.state = PipelineState.OUTPUT
            current_video = segment_states.get("enhanced", enhanced_result)
            output_result = self.delivery.export(current_video, request)
            segment_states["output"] = output_result

            self.state = PipelineState.COMPLETE
            return PipelineResult(
                success=True,
                output_path=output_result.get("path"),
                segments=segment_states,
                metadata={"duration": request.duration_seconds, "format": request.output_format},
            )

        except Exception as e:
            self.state = PipelineState.FAILED
            return PipelineResult(success=False, error=str(e), segments=segment_states)

    def _parse_intent(self, prompt: str, **overrides) -> VideoRequest:
        topic = overrides.get("topic", prompt)
        return VideoRequest(
            prompt=prompt,
            topic=topic,
            tone=overrides.get("tone", "professional"),
            language=overrides.get("language", self.config["tts"]["language"]),
            duration_seconds=overrides.get("duration_seconds", 60),
            avatar_id=overrides.get("avatar_id"),
            voice_id=overrides.get("voice_id"),
            source_files=overrides.get("source_files", []),
            output_format=overrides.get("output_format", self.config["output"]["format"]),
        )

    def _rerun_segment(self, segment_key: str, states: dict, request: VideoRequest) -> dict:
        if segment_key == "script":
            return self.script_skill.generate(request)
        elif segment_key == "visual":
            return self.visual_skill.build(states.get("script", {}), request)
        elif segment_key == "avatar":
            return self.avatar_engine.render(states.get("script", {}), states.get("visual", {}), request)
        elif segment_key == "enhanced":
            return self.enhancement.run(states.get("avatar", {}), request)
        return {}
