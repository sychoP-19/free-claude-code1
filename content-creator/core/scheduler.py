"""core/scheduler.py — APScheduler wrapper for scheduled pipeline runs.

Persists jobs to the SQLite `schedules` table, loads them at startup, and
re-runs them on cron triggers. Pipelines are looked up via the orchestrator's
PIPELINE_REGISTRY.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core import db
from core.orchestrator import PIPELINE_REGISTRY

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def _execute(schedule_id: int) -> None:
    """Called by APScheduler when a job fires."""
    rows = [r for r in db.list_schedules() if r["id"] == schedule_id]
    if not rows:
        return
    row = rows[0]
    pipeline = row["pipeline"]
    params = json.loads(row["params_json"] or "{}")
    runner = PIPELINE_REGISTRY.get(pipeline)
    if not runner:
        logger.warning("schedule %s references unknown pipeline %s", schedule_id, pipeline)
        return
    logger.info("schedule %s firing → %s(%s)", schedule_id, pipeline, params)
    db.update_schedule(schedule_id, last_run=time.time())
    try:
        await runner(params)
    except Exception as e:
        logger.exception("schedule %s failed: %s", schedule_id, e)


def add(name: str, cron_expr: str, pipeline: str, params: dict) -> int:
    """Persist a new schedule and register it with APScheduler."""
    sid = db.insert_schedule(name=name, cron=cron_expr, pipeline=pipeline, params=params)
    _register(sid, cron_expr)
    return sid


def remove(schedule_id: int) -> None:
    sched = get_scheduler()
    job_id = f"job-{schedule_id}"
    if sched.get_job(job_id):
        sched.remove_job(job_id)
    db.delete_schedule(schedule_id)


def toggle(schedule_id: int, enabled: bool) -> None:
    db.update_schedule(schedule_id, enabled=1 if enabled else 0)
    sched = get_scheduler()
    job_id = f"job-{schedule_id}"
    if enabled:
        rows = [r for r in db.list_schedules() if r["id"] == schedule_id]
        if rows:
            _register(schedule_id, rows[0]["cron"])
    else:
        if sched.get_job(job_id):
            sched.remove_job(job_id)


def _register(schedule_id: int, cron_expr: str) -> None:
    sched = get_scheduler()
    try:
        trigger = _parse_trigger(cron_expr)
        sched.add_job(_execute, trigger=trigger, id=f"job-{schedule_id}",
                      args=[schedule_id], replace_existing=True, max_instances=1)
        # Update next_run_at for UI display
        job = sched.get_job(f"job-{schedule_id}")
        if job and job.next_run_time:
            db.update_schedule(schedule_id, next_run=job.next_run_time.timestamp())
    except Exception as e:
        logger.warning("could not register schedule %s (%s): %s", schedule_id, cron_expr, e)


def _parse_trigger(expr: str) -> CronTrigger:
    """Accepts either a 5-field cron (`m h d M w`) or shorthand like `@hourly`."""
    expr = expr.strip()
    if expr.startswith("@"):
        shorthands = {
            "@yearly":   "0 0 1 1 *",
            "@annually": "0 0 1 1 *",
            "@monthly":  "0 0 1 * *",
            "@weekly":   "0 0 * * 0",
            "@daily":    "0 0 * * *",
            "@hourly":   "0 * * * *",
        }
        expr = shorthands.get(expr, "0 * * * *")
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError(f"cron must have 5 fields, got {len(parts)}")
    minute, hour, day, month, dow = parts
    return CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=dow)


def start() -> None:
    """Call at app startup to load persisted schedules and start scheduling."""
    sched = get_scheduler()
    if sched.running:
        return
    for row in db.list_schedules():
        if row["enabled"]:
            _register(row["id"], row["cron"])
    sched.start()


def shutdown() -> None:
    sched = get_scheduler()
    if sched.running:
        sched.shutdown(wait=False)
