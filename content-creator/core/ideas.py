"""core/ideas.py — idea inbox + AI ranker.

Stores raw ideas (text + optional source URL), asks Ollama to score each on a
0-10 virality × effort × goal-fit composite, and exposes a ranked queue. Top
ideas can be promoted to a pipeline run with one click.
"""
from __future__ import annotations

import json
import re

from core import db
from pipelines.base import build_system_prompt
from pipelines.llm import chat


def add(text: str, source: str = "manual") -> dict:
    """Insert an idea and return the row (score is 0 until rank() runs)."""
    idea_id = db.insert_idea(text=text, source=source, score=0.0)
    return {"id": idea_id, "text": text, "source": source, "score": 0.0}


def list_all(status: str | None = None, limit: int = 60) -> list[dict]:
    return db.list_ideas(status=status, limit=limit)


def update(idea_id: int, **fields) -> None:
    db.update_idea(idea_id, **fields)


async def rank_unscored(limit: int = 20) -> dict:
    """Ask the strategist to score every idea with score == 0."""
    pending = [i for i in db.list_ideas(limit=200) if (i.get("score") or 0) == 0][:limit]
    if not pending:
        return {"scored": 0, "items": []}

    listing = "\n".join(f"[{i['id']}] {i['text'][:200]}" for i in pending)
    prompt = (
        "Score each idea (0-10) by composite of: virality, effort needed, "
        "and fit for a creator/builder audience. Return ONLY JSON array of "
        "{id, score, reason}.\n\n" + listing
    )
    try:
        reply = await chat(
            [{"role": "user", "content": prompt}],
            system=build_system_prompt("strategist"),
            max_tokens=800,
        )
        m = re.search(r"\[.*\]", reply, re.DOTALL)
        if not m:
            return {"scored": 0, "items": [], "error": "no JSON in reply"}
        arr = json.loads(m.group())
        scored: list[dict] = []
        for s in arr:
            try:
                idea_id = int(s.get("id"))
                score = float(s.get("score"))
                db.update_idea(idea_id, score=score)
                scored.append({"id": idea_id, "score": score, "reason": s.get("reason", "")})
            except (TypeError, ValueError):
                continue
        return {"scored": len(scored), "items": scored}
    except Exception as e:
        return {"scored": 0, "items": [], "error": str(e)}
