"""core/orchestrator.py — multi-agent goal coordinator.

Takes a high-level goal, decides which pipelines to chain, and runs them
sequentially, emitting unified agent events. The five agent roles
(researcher, strategist, writer, designer, publisher) already emit events
from inside each pipeline; this layer adds plan/dispatch on top so the user
can say "make me a YouTube package about X" and get research + script + video.

New agents (v3.1):
  MonetizationAgent — analyses content and returns posting-time, engagement
    score, per-platform hashtags, and revenue-potential label.
  TrendScoutAgent — fetches Google Trends RSS + Reddit hot posts and returns
    top-5 trending topics scored by virality potential.  No API key required.
"""
from __future__ import annotations

import asyncio
import hashlib
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

import httpx

from core import db
from core.websocket_manager import manager
from pipelines import blog, carousel, longform, podcast, research, shorts

PIPELINE_REGISTRY = {
    "shorts":   shorts.run,
    "longform": longform.run,
    "podcast":  podcast.run,
    "blog":     blog.run,
    "carousel": carousel.run,
    "research": research.run,
}

AGENTS = ("researcher", "strategist", "writer", "designer", "publisher",
          "monetization", "trend-scout")


@dataclass
class GoalRun:
    goal: str
    plan: list[dict]
    started: float


_active: dict[str, GoalRun] = {}


# ── Core emitter ──────────────────────────────────────────────────────────────

async def emit(agent: str, kind: str, message: str, run_id: int | None = None) -> None:
    """Convenience emitter used by the orchestrator itself."""
    db.log_event(agent, kind, message, run_id=run_id)
    try:
        await manager.broadcast({
            "type": "agent_event", "run_id": run_id,
            "agent": agent, "kind": kind, "message": message, "ts": time.time(),
        })
    except Exception:
        pass


def active_agents() -> dict:
    """For topbar pulse: how many agents are currently 'thinking'."""
    cutoff = time.time() - 30  # seconds
    recent = db.recent_events(limit=60)
    counts = {a: 0 for a in AGENTS}
    for ev in recent:
        if ev["ts"] < cutoff:
            continue
        if ev["kind"] in ("think", "act") and ev["agent"] in counts:
            counts[ev["agent"]] += 1
    return {"counts": counts, "total": sum(counts.values())}


# ── Goal planner ──────────────────────────────────────────────────────────────

def plan_from_goal(goal: str) -> list[dict]:
    """Decide which pipelines to chain. Simple intent matching; the LLM can
    override later via /api/orchestrator/plan."""
    g = goal.lower()
    plan: list[dict] = [{"pipeline": "research", "params": {"topic": goal}}]
    if any(w in g for w in ("podcast", "audio", "episode")):
        plan.append({"pipeline": "podcast", "params": {"topic": goal}})
    if any(w in g for w in ("blog", "article", "post")):
        plan.append({"pipeline": "blog", "params": {"topic": goal}})
    if any(w in g for w in ("carousel", "slides", "instagram", "linkedin")):
        plan.append({"pipeline": "carousel", "params": {"topic": goal}})
    if any(w in g for w in ("video", "youtube", "long-form", "longform")):
        plan.append({"pipeline": "longform", "params": {"topic": goal}})
    if any(w in g for w in ("short", "shorts", "tiktok", "reel")) and "youtube_url" in goal.lower():
        url_match = re.search(r"https?://\S+", goal)
        if url_match:
            plan.append({"pipeline": "shorts", "params": {"youtube_url": url_match.group(), "num_clips": 3}})
    # If only research was added, also kick off blog as default deliverable
    if len(plan) == 1:
        plan.append({"pipeline": "blog", "params": {"topic": goal}})
    return plan


async def run_goal(goal: str, plan: list[dict] | None = None) -> dict:
    """Execute a chained goal. Returns combined results."""
    if not plan:
        plan = plan_from_goal(goal)
    run_key = f"goal-{int(time.time())}"
    _active[run_key] = GoalRun(goal=goal, plan=plan, started=time.time())
    await emit("strategist", "think", f"Goal received: {goal}")
    await emit("strategist", "act",   f"Plan: {' → '.join(p['pipeline'] for p in plan)}")

    results: list[dict] = []
    for step in plan:
        pipeline_name = step["pipeline"]
        runner = PIPELINE_REGISTRY.get(pipeline_name)
        if not runner:
            await emit("publisher", "error", f"unknown pipeline: {pipeline_name}")
            results.append({"pipeline": pipeline_name, "ok": False, "error": "unknown pipeline"})
            continue
        await emit("publisher", "act", f"Dispatching {pipeline_name}")
        try:
            res = await runner(step.get("params", {}))
            results.append(res)
            await emit("publisher", "done" if res.get("ok") else "error",
                       f"{pipeline_name}: {'ok' if res.get('ok') else res.get('error')}")
        except Exception as e:
            results.append({"pipeline": pipeline_name, "ok": False, "error": str(e)})
            await emit("publisher", "error", f"{pipeline_name} raised: {e}")

    _active.pop(run_key, None)
    return {
        "goal": goal,
        "plan": plan,
        "results": results,
        "elapsed_s": round(time.time() - _active.get(run_key, GoalRun(goal, plan, time.time())).started, 1),
    }


async def evaluate_run(run_id: int) -> str:
    """Self-improvement loop: ask the strategist what could improve the output."""
    from pipelines.llm import chat
    events = db.recent_events(limit=200, run_id=run_id)
    if not events:
        return "no events for run"
    summary = "\n".join(f"- [{e['agent']}/{e['kind']}] {e['message']}" for e in events[:50])
    prompt = (
        "You just observed this production run end-to-end. List 3-5 concrete improvements "
        "for next time. Be specific (prompt tweaks, structural changes, prompts to ban).\n\n"
        f"Run events:\n{summary}"
    )
    try:
        suggestion = await chat([{"role": "user", "content": prompt}], max_tokens=600, run_id=run_id)
        await emit("strategist", "think", f"Self-eval for run {run_id}: {suggestion[:140]}…")
        return suggestion
    except Exception as e:
        return f"self-eval failed: {e}"


# ═════════════════════════════════════════════════════════════════════════════
# MonetizationAgent
# ═════════════════════════════════════════════════════════════════════════════

# Best posting windows by platform (hour ranges in UTC, day-of-week 0=Mon).
_POSTING_WINDOWS: dict[str, list[dict]] = {
    "youtube": [
        {"day": "Thursday", "utc_hour_start": 15, "utc_hour_end": 17, "label": "Thu 15-17 UTC"},
        {"day": "Saturday", "utc_hour_start": 12, "utc_hour_end": 14, "label": "Sat 12-14 UTC"},
    ],
    "tiktok": [
        {"day": "Tuesday",  "utc_hour_start": 18, "utc_hour_end": 20, "label": "Tue 18-20 UTC"},
        {"day": "Friday",   "utc_hour_start": 19, "utc_hour_end": 21, "label": "Fri 19-21 UTC"},
    ],
    "instagram": [
        {"day": "Wednesday", "utc_hour_start": 11, "utc_hour_end": 13, "label": "Wed 11-13 UTC"},
        {"day": "Friday",    "utc_hour_start": 10, "utc_hour_end": 12, "label": "Fri 10-12 UTC"},
    ],
    "linkedin": [
        {"day": "Tuesday",   "utc_hour_start": 8,  "utc_hour_end": 10, "label": "Tue 08-10 UTC"},
        {"day": "Wednesday", "utc_hour_start": 9,  "utc_hour_end": 11, "label": "Wed 09-11 UTC"},
    ],
    "twitter": [
        {"day": "Wednesday", "utc_hour_start": 12, "utc_hour_end": 14, "label": "Wed 12-14 UTC"},
        {"day": "Thursday",  "utc_hour_start": 18, "utc_hour_end": 20, "label": "Thu 18-20 UTC"},
    ],
}

_PLATFORM_HASHTAG_LIMITS = {
    "youtube": 5,
    "tiktok": 8,
    "instagram": 15,
    "linkedin": 5,
    "twitter": 3,
}

# Simple keyword → hashtag pools keyed by content category.
_HASHTAG_POOL: dict[str, list[str]] = {
    "tech":    ["#tech", "#ai", "#coding", "#developer", "#innovation", "#software",
                "#programming", "#machinelearning", "#startup", "#saas"],
    "finance": ["#finance", "#investing", "#money", "#stocks", "#crypto", "#wealth",
                "#personalfinance", "#trading", "#entrepreneur", "#passiveincome"],
    "health":  ["#health", "#fitness", "#wellness", "#nutrition", "#workout", "#mindset",
                "#gym", "#mentalhealth", "#selfcare", "#lifestyle"],
    "gaming":  ["#gaming", "#gamer", "#livestream", "#esports", "#ps5", "#xbox",
                "#pcgaming", "#twitch", "#youtube", "#videogames"],
    "general": ["#viral", "#trending", "#content", "#creator", "#tips", "#learn",
                "#motivation", "#howto", "#tutorial", "#growth"],
}


def _detect_category(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ("code", "software", "ai", "tech", "developer", "program", "llm")):
        return "tech"
    if any(w in t for w in ("money", "invest", "stock", "crypto", "finance", "earn", "profit")):
        return "finance"
    if any(w in t for w in ("health", "fit", "workout", "gym", "diet", "wellness")):
        return "health"
    if any(w in t for w in ("game", "gaming", "play", "esport", "stream")):
        return "gaming"
    return "general"


def _engagement_score(text: str, platform: str) -> int:
    """Heuristic 0-100 engagement score based on content signals."""
    score = 40  # baseline
    t = text.lower()
    # question hooks
    if "?" in text:
        score += 8
    # list or numbered content
    if re.search(r"\b(top \d|best \d|\d+ ways|\d+ tips)", t):
        score += 10
    # emotional/power words
    power_words = ("secret", "hack", "reveal", "never", "always", "massive",
                   "free", "instantly", "proven", "ultimate", "surprising")
    score += sum(3 for w in power_words if w in t)
    # platform bonuses
    if platform == "tiktok":
        score += 5  # short-form favours discovery
    if platform == "youtube" and len(text) > 60:
        score += 5  # longer titles do better on YT
    return min(score, 100)


def _revenue_label(score: int) -> str:
    if score >= 80:
        return "viral"
    if score >= 65:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


@dataclass
class MonetizationAgent:
    """Analyses content and returns monetization metadata.

    No external API required — uses heuristics + optional Ollama for hashtag
    enrichment. Emits progress events to the WebSocket via db.log_event().
    """

    run_id: int | None = None

    async def analyse(self, content: str, platforms: list[str] | None = None) -> dict[str, Any]:
        if platforms is None:
            platforms = ["youtube", "tiktok", "instagram"]

        await emit("monetization", "think",
                   f"Analysing content ({len(content)} chars) for {platforms}", self.run_id)

        category = _detect_category(content)
        hashtag_pool = _HASHTAG_POOL.get(category, _HASHTAG_POOL["general"])

        # Per-platform analysis
        platform_data: dict[str, dict] = {}
        for plat in platforms:
            limit = _PLATFORM_HASHTAG_LIMITS.get(plat, 5)
            # Deterministic shuffle based on content hash so same input → same tags
            seed = int(hashlib.md5((content[:64] + plat).encode()).hexdigest(), 16) % (2**31)
            import random
            rng = random.Random(seed)
            tags = rng.sample(hashtag_pool, min(limit, len(hashtag_pool)))
            # Add platform-specific tag
            tags.insert(0, f"#{plat}")

            score = _engagement_score(content, plat)
            windows = _POSTING_WINDOWS.get(plat, _POSTING_WINDOWS["youtube"])

            platform_data[plat] = {
                "best_posting_times": windows,
                "engagement_score": score,
                "hashtags": tags,
                "revenue_potential": _revenue_label(score),
            }

        await emit("monetization", "act",
                   f"Scored across {len(platforms)} platforms — category: {category}", self.run_id)

        # Overall aggregate score (mean)
        avg_score = int(sum(v["engagement_score"] for v in platform_data.values()) / len(platform_data))

        result = {
            "category": category,
            "overall_engagement_score": avg_score,
            "overall_revenue_potential": _revenue_label(avg_score),
            "platforms": platform_data,
        }

        await emit("monetization", "done",
                   f"Monetization analysis complete — overall score {avg_score}/100, "
                   f"potential: {result['overall_revenue_potential']}", self.run_id)
        return result


# ═════════════════════════════════════════════════════════════════════════════
# TrendScoutAgent
# ═════════════════════════════════════════════════════════════════════════════

_GOOGLE_TRENDS_RSS = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
_REDDIT_HOT_JSON   = "https://www.reddit.com/r/{sub}/hot.json?limit=10&raw_json=1"
_DEFAULT_SUBREDDITS = ["technology", "artificial", "entrepreneur", "marketing", "business"]

_VIRALITY_KEYWORDS = (
    "AI", "viral", "hack", "secret", "million", "billion", "ban", "leak",
    "breaking", "crash", "surge", "record", "new", "launch", "free", "open",
)


def _virality_score(text: str) -> int:
    """0-100 virality score for a trend title."""
    score = 30
    t = text.lower()
    score += sum(4 for kw in _VIRALITY_KEYWORDS if kw.lower() in t)
    if len(text) < 50:
        score += 5   # short titles tend to spread faster
    if "?" in text:
        score += 5
    return min(score, 100)


async def _fetch_google_trends(client: httpx.AsyncClient) -> list[dict]:
    """Parse Google Trends daily RSS feed (no auth needed)."""
    topics: list[dict] = []
    try:
        r = await client.get(_GOOGLE_TRENDS_RSS, timeout=8)
        if r.status_code != 200:
            return topics
        root = ET.fromstring(r.text)
        for item in root.iter("item"):
            title_el = item.find("title")
            if title_el is None or not title_el.text:
                continue
            title = title_el.text.strip()
            # traffic element: <ht:approx_traffic>200,000+</ht:approx_traffic>
            traffic_el = item.find("{https://trends.google.com/trends/trendingsearches/daily}approx_traffic")
            traffic_raw = (traffic_el.text or "0+") if traffic_el is not None else "0+"
            traffic_num = int(re.sub(r"[^\d]", "", traffic_raw) or "0")
            topics.append({
                "title": title,
                "source": "google_trends",
                "traffic": traffic_num,
                "virality_score": _virality_score(title),
            })
    except Exception:
        pass
    return topics


async def _fetch_reddit_hot(client: httpx.AsyncClient, subreddits: list[str]) -> list[dict]:
    """Fetch hot posts from Reddit JSON API (no auth needed for public subs)."""
    topics: list[dict] = []
    headers = {"User-Agent": "JARVIS-TrendScout/1.0"}
    for sub in subreddits:
        try:
            r = await client.get(
                _REDDIT_HOT_JSON.format(sub=sub),
                headers=headers,
                timeout=8,
                follow_redirects=True,
            )
            if r.status_code != 200:
                continue
            data = r.json()
            for post in data.get("data", {}).get("children", []):
                p = post.get("data", {})
                title = p.get("title", "").strip()
                if not title:
                    continue
                score = p.get("score", 0)
                topics.append({
                    "title": title,
                    "source": f"reddit/r/{sub}",
                    "traffic": score,
                    "virality_score": _virality_score(title),
                })
        except Exception:
            continue
    return topics


@dataclass
class TrendScoutAgent:
    """Fetches trending topics from Google Trends RSS and Reddit.

    Returns top-5 topics scored by virality potential.
    No API keys required.
    """

    run_id: int | None = None
    subreddits: list[str] = field(default_factory=lambda: list(_DEFAULT_SUBREDDITS))

    async def scout(self, niche: str = "", limit: int = 5) -> dict[str, Any]:
        await emit("trend-scout", "think",
                   f"Scouting trends (niche: '{niche or 'all'}', limit: {limit})", self.run_id)

        async with httpx.AsyncClient() as client:
            google_task  = _fetch_google_trends(client)
            reddit_task  = _fetch_reddit_hot(client, self.subreddits)
            google_topics, reddit_topics = await asyncio.gather(google_task, reddit_task)

        all_topics = google_topics + reddit_topics

        # If a niche is specified, boost score for matching topics
        if niche:
            niche_lower = niche.lower()
            for t in all_topics:
                if niche_lower in t["title"].lower():
                    t["virality_score"] = min(t["virality_score"] + 15, 100)

        # Sort by composite: virality_score * 0.6 + normalised traffic * 0.4
        max_traffic = max((t["traffic"] for t in all_topics), default=1) or 1
        for t in all_topics:
            t["composite"] = (
                t["virality_score"] * 0.6
                + (t["traffic"] / max_traffic) * 100 * 0.4
            )

        ranked = sorted(all_topics, key=lambda x: x["composite"], reverse=True)
        top = ranked[:limit]

        # Clean up internal composite key before returning
        for t in top:
            t.pop("composite", None)

        await emit("trend-scout", "act",
                   f"Fetched {len(all_topics)} raw topics from "
                   f"{len(google_topics)} Google + {len(reddit_topics)} Reddit posts", self.run_id)
        await emit("trend-scout", "done",
                   f"Top trend: '{top[0]['title']}' (score {top[0]['virality_score']}/100)" if top
                   else "No trends found", self.run_id)

        return {
            "niche":       niche or "all",
            "total_found": len(all_topics),
            "topics":      top,
            "sources":     {"google_trends": len(google_topics), "reddit": len(reddit_topics)},
        }
