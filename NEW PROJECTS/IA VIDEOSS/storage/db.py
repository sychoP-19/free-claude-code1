"""Storage layer — SQLite for job state, asset tracking, and versioning."""

import sqlite3
import json
from pathlib import Path
from datetime import datetime


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    config TEXT,
                    result TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS segments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    segment_key TEXT NOT NULL,
                    state TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (job_id) REFERENCES jobs(id)
                )
            """)

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def save_job(self, job_id: str, prompt: str, status: str = "pending", config: dict = None):
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO jobs (id, prompt, status, config, updated_at) VALUES (?, ?, ?, ?, ?)",
                (job_id, prompt, status, json.dumps(config or {}), datetime.now().isoformat()),
            )

    def update_job(self, job_id: str, status: str, result: dict = None):
        with self._conn() as c:
            c.execute(
                "UPDATE jobs SET status=?, result=?, updated_at=? WHERE id=?",
                (status, json.dumps(result or {}), datetime.now().isoformat(), job_id),
            )

    def get_job(self, job_id: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row:
                return {"id": row[0], "prompt": row[1], "status": row[2], "config": json.loads(row[3] or "{}"), "result": json.loads(row[4] or "{}"), "created_at": row[5], "updated_at": row[6]}
        return None

    def list_jobs(self, limit: int = 20) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT id, prompt, status, created_at FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [{"id": r[0], "prompt": r[1], "status": r[2], "created_at": r[3]} for r in rows]
