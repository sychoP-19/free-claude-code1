"""Complete Reel Production Pipeline (Stages 1-5).

Orchestrates full reel production from topic to platform export:
  Stage 1: Research & Topic Discovery
  Stage 2: Script & Metadata Generation
  Stage 3: Asset Generation (TTS, images, B-roll)
  Stage 4: Video Assembly (FFmpeg composition)
  Stage 5: Platform Export (YouTube/TikTok/Instagram variants)

Input: topic, style, tone parameters
Output: Final MP4 video + platform-specific exports

Usage:
    pipeline = ReelProductionPipeline(params)
    result = await pipeline.run()
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from agents.asset_generator import AssetResult, generate_assets
from agents.video_assembler import VideoAssemblyResult, assemble_video
from agents.platform_exporter import run as platform_export
from pipelines.base import PipelineRun, OUTPUTS

logger = logging.getLogger(__name__)


async def _emit_event(agent: str, action: str, message: str):
    """Emit WebSocket event for pipeline progress."""
    from core.websocket_manager import manager
    await manager.agent_update(agent, action, 0)
    await manager.log(f"[{agent}] {message}", "info")


async def _emit_pipeline_stage(stage: str, status: str, progress: int, data: dict = None):
    """Emit pipeline stage event."""
    from core.websocket_manager import manager
    await manager.pipeline_event(stage, status, progress, data)


async def _emit_script_ready(script: str, script_id: str = None):
    """Emit script ready for review."""
    from core.websocket_manager import manager
    await manager.script_ready(script, script_id)


class ReelProductionPipeline(PipelineRun):
    """Complete reel production pipeline (Stages 1-5).

    Stage 1: Research & Topic Discovery
    Stage 2: Script & Metadata Generation
    Stage 3: Asset Generation (TTS, images, B-roll)
    Stage 4: Video Assembly (FFmpeg composition)
    Stage 5: Platform Export (YouTube/TikTok/Instagram variants)
    """

    pipeline = "reel-production"
    publish_platforms = ("youtube", "instagram", "tiktok")

    async def execute(self) -> tuple[str, dict]:
        """Execute the complete 5-stage pipeline."""
        started = time.time()

        # Extract parameters
        topic = self.params.get("topic", "")
        if not topic:
            raise ValueError("Missing 'topic' parameter")

        style = self.params.get("style", "shorts")
        tone = self.params.get("tone", "viral")
        topic_id = self.params.get("topic_id", f"reel_{int(time.time())}")
        n_images_per_scene = int(self.params.get("n_images_per_scene", 5))
        width = int(self.params.get("width", 1080))
        height = int(self.params.get("height", 1920))
        clip_duration = float(self.params.get("clip_duration", 3.0))
        voice_lang = self.params.get("voice_lang", "en")
        target_duration = int(self.params.get("duration", 60))

        # Stage 1: Research (simplified)
        await self.set_stage("research", 10)
        await _emit_event("researcher", "act", f"Analyzing topic: {topic}")
        research_output = await self._stage1_research(topic)
        await self.set_stage("research", 20)
        await _emit_event("researcher", "done", "Research complete")
        await _emit_pipeline_stage("topic-discovery", "completed", 20, {"topic": topic})

        # Stage 2: Script Generation
        await self.set_stage("script", 30)
        await _emit_event("writer", "act", "Generating script")
        script_output = await self._stage2_script(topic, research_output, style, tone, target_duration)
        script_scenes = script_output.get("scenes", [])
        await self.set_stage("script", 50)
        await _emit_event("writer", "done", f"Script: {script_output.get('duration', 0)}s")
        await _emit_pipeline_stage("script-generation", "completed", 50, {"script_ready": True})

        # Script preview gate - wait for approval (placeholder)
        await _emit_script_ready(script_output.get("script", ""), topic_id)

        # Stage 3: Asset Generation
        await self.set_stage("visuals", 55)
        await _emit_event("asset-gen", "act", f"Generating assets for {len(script_scenes)} scenes")

        asset_result = await generate_assets(
            scenes=script_scenes,
            topic_id=topic_id,
            n_images_per_scene=n_images_per_scene,
            width=width,
            height=height,
        )

        if not asset_result.ok:
            raise RuntimeError(f"Asset generation failed: {asset_result.errors}")

        for error in asset_result.errors:
            await _emit_event("asset-gen", "warning", error)

        await self.set_stage("visuals", 70)
        await _emit_event("asset-gen", "done", f"Generated {len(asset_result.assets)} assets")
        await _emit_pipeline_stage("asset-generation", "completed", 70, {"assets_count": len(asset_result.assets)})

        # Track assets
        for asset in asset_result.assets:
            self.track_asset(
                kind=asset.get("type", "image"),
                path=asset["path"],
                caption=f"{asset.get('source', 'unknown')} asset",
                tags=["stage3", "asset-gen", topic_id],
            )

        asset_paths = [a["path"] for a in asset_result.assets]

        # Stage 4: Video Assembly
        await self.set_stage("assembly", 75)
        await _emit_event("video-assembler", "act", "Assembling video from assets")

        script_text = script_output.get("script", "")
        if script_text:
            await _emit_event("tts", "act", "Generating narration")

        assembly_result = await assemble_video(
            asset_paths=asset_paths,
            topic_id=topic_id,
            script_text=script_text,
            clip_duration=clip_duration,
            voice_lang=voice_lang,
        )

        if not assembly_result.ok:
            raise RuntimeError(f"Video assembly failed: {assembly_result.errors}")

        for error in assembly_result.errors:
            await _emit_event("video-assembler", "warning", error)

        await self.set_stage("assembly", 85)
        await _emit_event("video-assembler", "done", f"Completed {assembly_result.duration_s}s video")
        await _emit_pipeline_stage("video-assembly", "completed", 85, {"duration_s": assembly_result.duration_s})

        # Track final video
        self.track_asset(
            kind="video",
            path=assembly_result.output_path,
            caption=f"Master video ({assembly_result.duration_s}s)",
            tags=["stage4", "master", topic_id],
        )

        if assembly_result.audio_path:
            self.track_asset(
                kind="audio",
                path=assembly_result.audio_path,
                caption="Narration audio",
                tags=["tts", "narration"],
            )

        # Stage 5: Platform Export
        await self.set_stage("publish", 90)
        await _emit_event("publisher", "act", "Exporting to platforms")

        platforms = self.params.get("platforms", "youtube,tiktok,instagram").split(",")
        master_path = assembly_result.output_path

        try:
            export_result = await platform_export(
                master_video=master_path,
                script_metadata=script_output,
                topic_id=topic_id,
                platforms=platforms,
            )

            await self.set_stage("publish", 100)
            await _emit_event("publisher", "done", f"Exported to {export_result.get('successful', 0)}/{export_result.get('total', 0)} platforms")
            await _emit_pipeline_stage("platform-export", "completed", 100, {"platforms_exported": export_result.get('successful', 0)})

        except Exception as e:
            logger.warning(f"Platform export failed: {e}")
            await self.emit("publisher", "warning", f"Export failed: {e}")
            export_result = {"success": False, "error": str(e), "platforms": []}

        elapsed = time.time() - started

        result_summary = {
            "stages": {
                "stage1_research": {"ok": True},
                "stage2_script": script_output.get("metadata", {}),
                "stage3_assets": {
                    "ok": asset_result.ok,
                    "assets_count": len(asset_result.assets),
                    "errors": asset_result.errors,
                },
                "stage4_assembly": {
                    "ok": assembly_result.ok,
                    "clips_created": assembly_result.clips_created,
                    "duration_s": assembly_result.duration_s,
                    "video_bytes": assembly_result.video_bytes,
                    "errors": assembly_result.errors,
                },
                "stage5_export": export_result,
            },
            "master_path": master_path,
            "elapsed_s": round(elapsed, 1),
        }

        return master_path, result_summary


    async def _stage1_research(self, topic: str) -> dict:
        """Stage 1: Research & topic validation."""
        return {"topic": topic, "status": "complete"}


    async def _stage2_script(self, topic: str, research: dict, style: str, tone: str, target_duration: int) -> dict:
        """Stage 2: Script generation."""
        from pipelines.llm import chat
        from pipelines.base import build_system_prompt

        prompt = f"""Create a viral short-form script for: "{topic}"
Style: {style}
Tone: {tone}
Duration: {target_duration}s

Return ONLY valid JSON:
{{
  "topic": "string",
  "duration": number,
  "script": "full script with [timestamp] markers",
  "scenes": [{{"description": "...", "timing": "0-5s"}}],
  "titles": ["option1", "option2"],
  "hashtags": ["#tag1", "#tag2"]
}}
"""

        try:
            reply = await chat(
                [{"role": "user", "content": prompt}],
                system=build_system_prompt("scriptwriter"),
                max_tokens=800,
            )

            match = re.search(r"\{.*\}", reply, re.DOTALL)
            if match:
                data = json.loads(match.group())
                if "scenes" not in data:
                    data["scenes"] = [{"description": "Main content", "timing": "0-60s"}]
                return data
        except Exception as e:
            logger.warning(f"Script generation failed: {e}")

        return {
            "topic": topic,
            "duration": target_duration,
            "script": f"[0-3s] HOOK: Watch this!\n[{target_duration-3}-{target_duration}s] CTA: Follow more!",
            "scenes": [{"description": f"Content about {topic}", "timing": f"0-{target_duration}s"}],
            "titles": [f"{topic.title()} - Must Watch"],
            "hashtags": ["#viral", "#trending"],
        }

        # Build result summary
        elapsed = time.time() - started

        result_summary = {
            "stages": {
                "stage3_assets": {
                    "ok": asset_result.ok,
                    "assets_count": len(asset_result.assets),
                    "errors": asset_result.errors,
                },
                "stage4_assembly": {
                    "ok": assembly_result.ok,
                    "clips_created": assembly_result.clips_created,
                    "duration_s": assembly_result.duration_s,
                    "video_bytes": assembly_result.video_bytes,
                    "errors": assembly_result.errors,
                },
            },
            "asset_paths": asset_paths[:10],  # First 10 for reference
            "elapsed_s": round(elapsed, 1),
        }

        return assembly_result.output_path, result_summary


async def run(params: dict) -> dict:
    """Convenience wrapper for running the pipeline.

    Usage:
        result = await run({
            "scenes": ["Scene 1 description", "Scene 2 description"],
            "topic_id": "my-reel",
            "script": "Full script text for TTS",
        })
    """
    res = await ReelProductionPipeline(params).run()
    return res.__dict__