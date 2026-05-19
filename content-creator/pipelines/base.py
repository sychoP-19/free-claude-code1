"""pipelines/base.py — shared run lifecycle for every pipeline.

Every pipeline subclasses PipelineRun. The base handles:
- Recording the run in SQLite (start/finish + status)
- Emitting agent events via WebSocket + DB
- Standard 5-stage progress strip (research, script, visuals, audio, assembly)
- Publish-to-folder hook (copy final asset to outputs/ready-to-publish/<platform>/<date>/)
- Brand voice injection into prompts
"""
from __future__ import annotations

import asyncio
import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core import db
from core.websocket_manager import manager

BASE       = Path(__file__).parent.parent
OUTPUTS    = BASE / "outputs"
PUBLISH    = OUTPUTS / "ready-to-publish"
BRAND_FILE = BASE / "data" / "brand_voice.json"

STAGES = ["research", "script", "visuals", "audio", "assembly"]


@dataclass
class PipelineResult:
    ok: bool
    run_id: int
    pipeline: str
    output_path: str = ""
    assets: list[dict] = field(default_factory=list)
    error: str = ""
    elapsed_s: float = 0.0
    extra: dict = field(default_factory=dict)


def load_brand_voice() -> dict:
    """Read brand voice settings; returns sane defaults if missing."""
    if BRAND_FILE.exists():
        try:
            return json.loads(BRAND_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "tone": "direct, energetic, slightly cinematic",
        "audience": "creators and builders",
        "banned_phrases": ["synergy", "leverage", "circle back"],
        "signature_opening": "",
        "language": "en",
        "improvements": [],
    }


def build_system_prompt(role: str = "assistant") -> str:
    bv = load_brand_voice()
    banned = ", ".join(bv.get("banned_phrases") or [])
    return (
        f"You are JARVIS's {role} agent.\n"
        f"Tone: {bv.get('tone','direct')}\n"
        f"Audience: {bv.get('audience','creators')}\n"
        f"Banned phrases (never use these): {banned}\n"
        f"Reply in: {bv.get('language','en')}\n"
        f"Be precise, helpful, and avoid marketing clichés."
    )


class PipelineRun:
    """Subclass and implement `execute()`. Use self.emit() and self.set_stage()."""

    pipeline: str = "abstract"
    publish_platforms: tuple[str, ...] = ()

    def __init__(self, params: dict):
        self.params = params
        self.run_id: int | None = None
        self.started = time.time()
        self.assets: list[dict] = []

    async def run(self) -> PipelineResult:
        self.run_id = db.start_run(self.pipeline, self.params)
        await self.emit("publisher", "act", f"{self.pipeline} run #{self.run_id} started")
        try:
            output_path, extra = await self.execute()
            for a in self.assets:
                db.insert_asset(self.run_id, **a)
            if output_path:
                self._publish(output_path)
            db.finish_run(self.run_id, ok=True, output_path=output_path)
            await self.emit("publisher", "done", f"{self.pipeline} complete: {output_path}")
            return PipelineResult(
                ok=True, run_id=self.run_id, pipeline=self.pipeline,
                output_path=output_path, assets=self.assets,
                elapsed_s=round(time.time() - self.started, 1), extra=extra or {},
            )
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            db.finish_run(self.run_id, ok=False, error=msg)
            await self.emit("publisher", "error", msg)
            return PipelineResult(
                ok=False, run_id=self.run_id, pipeline=self.pipeline,
                error=msg, elapsed_s=round(time.time() - self.started, 1),
            )

    async def execute(self) -> tuple[str, dict]:
        """Subclass returns (output_path, extra_dict). Raise on failure."""
        raise NotImplementedError

    # ── progress + agent events ────────────────────────────────────────────
    async def set_stage(self, stage: str, progress_pct: int = 0) -> None:
        try:
            await manager.broadcast({
                "type": "pipeline_stage",
                "run_id": self.run_id,
                "pipeline": self.pipeline,
                "stage": stage,
                "progress": progress_pct,
                "ts": time.time(),
            })
        except Exception:
            pass

    async def emit(self, agent: str, kind: str, message: str) -> None:
        db.log_event(agent, kind, message, run_id=self.run_id)
        try:
            await manager.broadcast({
                "type": "agent_event",
                "run_id": self.run_id,
                "agent": agent, "kind": kind, "message": message,
                "ts": time.time(),
            })
        except Exception:
            pass

    def track_asset(self, kind: str, path: str, caption: str = "", tags: list[str] | None = None) -> None:
        p = Path(path)
        size = p.stat().st_size if p.exists() else 0
        self.assets.append({"kind": kind, "path": str(p), "caption": caption,
                            "tags": tags or [], "size": size})

    # ── publish-to-folder ──────────────────────────────────────────────────
    def _publish(self, src_path: str) -> None:
        if not self.publish_platforms:
            return
        src = Path(src_path)
        if not src.exists() or src.stat().st_size == 0:
            return
        date = time.strftime("%Y-%m-%d")
        for platform in self.publish_platforms:
            dest_dir = PUBLISH / platform / date
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / src.name
            try:
                shutil.copy2(src, dest)
            except Exception:
                pass


def slugify(s: str, max_len: int = 60) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in s).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out[:max_len] or f"untitled-{int(time.time())}"
