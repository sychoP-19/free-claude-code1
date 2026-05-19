import asyncio
import json
from typing import Set
from fastapi import WebSocket


class WebSocketManager:
    def __init__(self):
        self._connections: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.add(ws)

    def disconnect(self, ws: WebSocket):
        self._connections.discard(ws)

    async def broadcast(self, data: dict):
        if not self._connections:
            return
        message = json.dumps(data)
        dead = set()
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._connections.discard(ws)

    async def log(self, text: str, level: str = "info"):
        await self.broadcast({"type": "log", "level": level, "text": text})

    async def agent_update(self, agent: str, status: str, progress: int = 0):
        await self.broadcast({"type": "agent_update", "agent": agent, "status": status, "progress": progress})

    async def metric(self, key: str, value):
        await self.broadcast({"type": "metric", "key": key, "value": value})

    async def notify(self, text: str, level: str = "info"):
        await self.broadcast({"type": "notify", "text": text, "level": level})

    async def pipeline_event(self, stage: str, status: str, progress: int = 0, data: dict = None):
        """Broadcast pipeline stage events."""
        payload = {"type": "pipeline_stage", "stage_id": stage, "status": status, "progress": progress}
        if data:
            payload.update(data)
        await self.broadcast(payload)

    async def script_ready(self, script: str, script_id: str = None):
        """Broadcast script ready for review."""
        await self.broadcast({"type": "script_ready", "script": script, "script_id": script_id})

    async def reel_complete(self, reel: dict):
        """Broadcast when reel is complete."""
        await self.broadcast({"type": "reel_complete", "reel": reel})


manager = WebSocketManager()
