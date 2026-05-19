"""core/asset_library.py — thin facade over db.search_assets with stats."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from core import db


def search(query: str = "", kind: str = "", limit: int = 60) -> list[dict]:
    rows = db.search_assets(query=query, kind=kind, limit=limit)
    out = []
    for r in rows:
        p = Path(r["path"])
        out.append({
            **r,
            "exists": p.exists(),
            "size_human": _human(r.get("bytes") or (p.stat().st_size if p.exists() else 0)),
        })
    return out


def stats() -> dict:
    rows = db.search_assets(limit=10_000)
    kinds = Counter(r["kind"] for r in rows)
    total_bytes = sum(r.get("bytes", 0) for r in rows)
    return {
        "total": len(rows),
        "by_kind": dict(kinds),
        "bytes_total": total_bytes,
        "bytes_human": _human(total_bytes),
    }


def _human(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    v = float(n)
    i = 0
    while v >= 1024 and i < len(units) - 1:
        v /= 1024
        i += 1
    return f"{v:.1f} {units[i]}"
