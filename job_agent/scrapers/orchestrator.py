"""Orchestrator — runs enabled scrapers and aggregates results."""

from __future__ import annotations

from typing import Any

from job_agent.matcher import match_job
from job_agent.scrapers import arabic_remote, global_remote, mexico


def run_all(
    keywords: list[str],
    locations: dict[str, bool],
) -> list[dict[str, Any]]:
    all_jobs: list[dict[str, Any]] = []
    if locations.get("global_remote", False):
        all_jobs.extend(global_remote.run(keywords))
    if locations.get("arabic_remote", False):
        all_jobs.extend(arabic_remote.run(keywords))
    if locations.get("mexico", False):
        all_jobs.extend(mexico.run(keywords))

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for job in all_jobs:
        url = job.get("url", "") or ""
        key = url if url else f"{job['title']}|{job['company']}"
        if key in seen:
            continue
        seen.add(key)
        desc = job.pop("description", "")
        score = match_job(job["title"], desc, keywords)
        job["match_score"] = score
        job["status"] = "New"
        deduped.append(job)

    deduped.sort(key=lambda j: j["match_score"], reverse=True)
    return deduped