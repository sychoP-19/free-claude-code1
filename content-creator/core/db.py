"""core/db.py — SQLite persistence for JARVIS.

One DB file (data/jarvis.db) holds: ideas, pipeline runs, generated assets,
LLM cost logs, agent events, scheduled jobs, and local analytics counters.

Schema is idempotent (CREATE TABLE IF NOT EXISTS). Call init_schema() once at
app startup. All helpers use short-lived connections (no shared state) so they
are safe across asyncio tasks.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable

_DB_PATH = Path(__file__).parent.parent / "data" / "jarvis.db"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB_PATH, isolation_level=None, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


SCHEMA = """
CREATE TABLE IF NOT EXISTS ideas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text        TEXT    NOT NULL,
    source      TEXT,
    score       REAL    DEFAULT 0,
    status      TEXT    DEFAULT 'new',     -- new | queued | done | rejected
    created_at  REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline     TEXT    NOT NULL,
    params_json  TEXT    NOT NULL,
    started_at   REAL    NOT NULL,
    finished_at  REAL,
    status       TEXT    NOT NULL,         -- running | ok | error
    output_path  TEXT,
    error        TEXT
);

CREATE TABLE IF NOT EXISTS assets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER REFERENCES runs(id) ON DELETE CASCADE,
    kind        TEXT    NOT NULL,          -- video | audio | image | text
    path        TEXT    NOT NULL,
    caption     TEXT,
    tags_json   TEXT,
    sha256      TEXT,
    bytes       INTEGER DEFAULT 0,
    created_at  REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assets_kind ON assets(kind);
CREATE INDEX IF NOT EXISTS idx_assets_run  ON assets(run_id);

CREATE TABLE IF NOT EXISTS costs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER REFERENCES runs(id) ON DELETE SET NULL,
    ts          REAL    NOT NULL,
    route       TEXT    NOT NULL,          -- proxy | ollama | pollinations | gtts | ffmpeg
    tokens_in   INTEGER DEFAULT 0,
    tokens_out  INTEGER DEFAULT 0,
    latency_ms  INTEGER DEFAULT 0,
    ok          INTEGER DEFAULT 1,
    note        TEXT
);
CREATE INDEX IF NOT EXISTS idx_costs_ts ON costs(ts);

CREATE TABLE IF NOT EXISTS agent_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER REFERENCES runs(id) ON DELETE CASCADE,
    agent       TEXT    NOT NULL,          -- researcher | strategist | writer | designer | publisher
    kind        TEXT    NOT NULL,          -- think | act | done | error
    message     TEXT    NOT NULL,
    ts          REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON agent_events(ts);

CREATE TABLE IF NOT EXISTS schedules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    cron        TEXT    NOT NULL,
    pipeline    TEXT    NOT NULL,
    params_json TEXT    NOT NULL,
    last_run    REAL,
    next_run    REAL,
    enabled     INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS analytics (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      REAL    NOT NULL,
    metric  TEXT    NOT NULL,
    value   REAL    NOT NULL,
    note    TEXT
);
CREATE INDEX IF NOT EXISTS idx_analytics ON analytics(metric, ts);

CREATE TABLE IF NOT EXISTS reel_pending (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id    TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    platform    TEXT    NOT NULL,
    selected_at REAL    NOT NULL,
    status      TEXT    DEFAULT 'pending',
    metadata_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_reel_pending_status ON reel_pending(status);

CREATE TABLE IF NOT EXISTS reel_completed (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id        TEXT    NOT NULL,
    title           TEXT    NOT NULL,
    platform        TEXT    NOT NULL,
    completed_at    REAL    NOT NULL,
    output_path     TEXT    NOT NULL,
    script_json     TEXT,
    duration_s      INTEGER,
    topic_title     TEXT
);
CREATE INDEX IF NOT EXISTS idx_reel_completed_topic ON reel_completed(topic_id);
CREATE INDEX IF NOT EXISTS idx_reel_completed_platform ON reel_completed(platform);
"""


def init_schema() -> None:
    with _conn() as c:
        c.executescript(SCHEMA)


# ── ideas ──────────────────────────────────────────────────────────────────
def insert_idea(text: str, source: str = "manual", score: float = 0.0) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO ideas (text, source, score, created_at) VALUES (?,?,?,?)",
            (text, source, score, time.time()),
        )
        return cur.lastrowid


def list_ideas(status: str | None = None, limit: int = 100) -> list[dict]:
    sql = "SELECT * FROM ideas"
    args: list = []
    if status:
        sql += " WHERE status=?"
        args.append(status)
    sql += " ORDER BY score DESC, created_at DESC LIMIT ?"
    args.append(limit)
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def update_idea(idea_id: int, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    args = list(fields.values()) + [idea_id]
    with _conn() as c:
        c.execute(f"UPDATE ideas SET {cols} WHERE id=?", args)


# ── runs ───────────────────────────────────────────────────────────────────
def start_run(pipeline: str, params: dict) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO runs (pipeline, params_json, started_at, status) VALUES (?,?,?,?)",
            (pipeline, json.dumps(params), time.time(), "running"),
        )
        return cur.lastrowid


def finish_run(run_id: int, ok: bool, output_path: str = "", error: str = "") -> None:
    with _conn() as c:
        c.execute(
            "UPDATE runs SET finished_at=?, status=?, output_path=?, error=? WHERE id=?",
            (time.time(), "ok" if ok else "error", output_path, error, run_id),
        )


def list_runs(pipeline: str | None = None, limit: int = 50) -> list[dict]:
    sql = "SELECT * FROM runs"
    args: list = []
    if pipeline:
        sql += " WHERE pipeline=?"
        args.append(pipeline)
    sql += " ORDER BY started_at DESC LIMIT ?"
    args.append(limit)
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


# ── assets ─────────────────────────────────────────────────────────────────
def insert_asset(run_id: int | None, kind: str, path: str, caption: str = "",
                 tags: Iterable[str] | None = None, sha256: str = "", size: int = 0) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO assets (run_id, kind, path, caption, tags_json, sha256, bytes, created_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (run_id, kind, path, caption, json.dumps(list(tags or [])), sha256, size, time.time()),
        )
        return cur.lastrowid


def search_assets(query: str = "", kind: str = "", limit: int = 60) -> list[dict]:
    sql = "SELECT * FROM assets WHERE 1=1"
    args: list = []
    if kind:
        sql += " AND kind=?"
        args.append(kind)
    if query:
        sql += " AND (caption LIKE ? OR tags_json LIKE ? OR path LIKE ?)"
        like = f"%{query}%"
        args.extend([like, like, like])
    sql += " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


# ── costs ──────────────────────────────────────────────────────────────────
def log_cost(route: str, tokens_in: int = 0, tokens_out: int = 0,
             latency_ms: int = 0, ok: bool = True, run_id: int | None = None,
             note: str = "") -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO costs (run_id, ts, route, tokens_in, tokens_out, latency_ms, ok, note)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (run_id, time.time(), route, tokens_in, tokens_out, latency_ms, 1 if ok else 0, note),
        )


def cost_summary(days: int = 7) -> dict:
    since = time.time() - days * 86400
    with _conn() as c:
        rows = c.execute(
            "SELECT route, COUNT(*) n, SUM(tokens_in) tin, SUM(tokens_out) tout,"
            " AVG(latency_ms) avg_ms, SUM(CASE WHEN ok=0 THEN 1 ELSE 0 END) fails"
            " FROM costs WHERE ts>=? GROUP BY route",
            (since,),
        ).fetchall()
        daily = c.execute(
            "SELECT CAST((ts - ?) / 86400 AS INTEGER) AS day,"
            " COUNT(*) n, SUM(tokens_in + tokens_out) total_tokens"
            " FROM costs WHERE ts>=? GROUP BY day ORDER BY day",
            (since, since),
        ).fetchall()
    return {
        "by_route": [dict(r) for r in rows],
        "daily":    [dict(r) for r in daily],
        "since":    since,
        "days":     days,
    }


# ── agent events ───────────────────────────────────────────────────────────
def log_event(agent: str, kind: str, message: str, run_id: int | None = None) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO agent_events (run_id, agent, kind, message, ts) VALUES (?,?,?,?,?)",
            (run_id, agent, kind, message, time.time()),
        )
        return cur.lastrowid


def recent_events(limit: int = 100, run_id: int | None = None) -> list[dict]:
    sql = "SELECT * FROM agent_events"
    args: list = []
    if run_id is not None:
        sql += " WHERE run_id=?"
        args.append(run_id)
    sql += " ORDER BY ts DESC LIMIT ?"
    args.append(limit)
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def mc_stats() -> dict:
    """Aggregate counters for Mission Control stats bar (last 24 h)."""
    today_start = time.time() - 86400
    with _conn() as c:
        runs_today = c.execute(
            "SELECT COUNT(*) FROM runs WHERE started_at >= ?", (today_start,)
        ).fetchone()[0]
        assets_gen = c.execute(
            "SELECT COUNT(*) FROM assets WHERE created_at >= ?", (today_start,)
        ).fetchone()[0]
        ideas_ranked = c.execute(
            "SELECT COUNT(*) FROM ideas WHERE score > 0"
        ).fetchone()[0]
        cost_tokens = c.execute(
            "SELECT COALESCE(SUM(tokens_in + tokens_out), 0) FROM costs WHERE ts >= ?",
            (today_start,),
        ).fetchone()[0]
    cost_usd = round((cost_tokens or 0) / 1000 * 0.002, 4)
    return {
        "runs_today":       runs_today,
        "assets_generated": assets_gen,
        "ideas_ranked":     ideas_ranked,
        "cost_usd":         cost_usd,
        "cost_tokens":      cost_tokens or 0,
    }


# ── schedules ──────────────────────────────────────────────────────────────
def insert_schedule(name: str, cron: str, pipeline: str, params: dict) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO schedules (name, cron, pipeline, params_json) VALUES (?,?,?,?)",
            (name, cron, pipeline, json.dumps(params)),
        )
        return cur.lastrowid


def list_schedules() -> list[dict]:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM schedules ORDER BY id DESC").fetchall()]


def update_schedule(sid: int, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    args = list(fields.values()) + [sid]
    with _conn() as c:
        c.execute(f"UPDATE schedules SET {cols} WHERE id=?", args)


def delete_schedule(sid: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM schedules WHERE id=?", (sid,))


# ── analytics ──────────────────────────────────────────────────────────────
def log_metric(metric: str, value: float, note: str = "") -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO analytics (ts, metric, value, note) VALUES (?,?,?,?)",
            (time.time(), metric, value, note),
        )


def analytics_summary(metric: str | None = None, days: int = 30) -> list[dict]:
    since = time.time() - days * 86400
    sql = "SELECT * FROM analytics WHERE ts>=?"
    args: list[Any] = [since]
    if metric:
        sql += " AND metric=?"
        args.append(metric)
    sql += " ORDER BY ts ASC"
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


# ── reel_pending ───────────────────────────────────────────────────────────
def reel_select_topic(topic_id: str, title: str, platform: str, metadata: dict | None = None) -> int:
    """Store user topic selection for reel production."""
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO reel_pending (topic_id, title, platform, selected_at, metadata_json) VALUES (?,?,?,?,?)",
            (topic_id, title, platform, time.time(), json.dumps(metadata or {})),
        )
        return cur.lastrowid


def reel_list_pending() -> list[dict]:
    """List all pending reel selections."""
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM reel_pending WHERE status='pending' ORDER BY selected_at DESC"
        ).fetchall()]


def reel_start_production(topic_id: str) -> bool:
    """Mark topic as being produced."""
    with _conn() as c:
        row = c.execute(
            "UPDATE reel_pending SET status='producing' WHERE topic_id=? AND status='pending'",
            (topic_id,),
        ).rowcount
        return row > 0


def reel_complete(topic_id: str, title: str, platform: str, output_path: str,
                  script: dict | None = None, duration_s: int = 0, topic_title: str = "") -> None:
    """Mark reel as completed and move to completed table."""
    with _conn() as c:
        c.execute(
            "DELETE FROM reel_pending WHERE topic_id=?",
            (topic_id,),
        )
        c.execute(
            "INSERT INTO reel_completed (topic_id, title, platform, completed_at, output_path, script_json, duration_s, topic_title) VALUES (?,?,?,?,?,?,?,?)",
            (topic_id, title, platform, time.time(), output_path, json.dumps(script or {}), duration_s, topic_title),
        )


def reel_get_completed(platform: str = "") -> list[dict]:
    """Get completed reels, optionally filtered by platform."""
    sql = "SELECT * FROM reel_completed"
    args: list = []
    if platform:
        sql += " WHERE platform=?"
        args.append(platform)
    sql += " ORDER BY completed_at DESC"
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]
