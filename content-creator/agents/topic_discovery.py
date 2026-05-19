"""topic_discovery.py — Topic Discovery with trend metrics & multi-platform support."""
import asyncio
import random
from datetime import datetime, timedelta

import httpx

from agents.trending_agent import get_trending_topics

# ─── Mock Metric Generators ───────────────────────────────────────────────────

def _generate_trend_score() -> int:
    """Generate a realistic trend score (0-100)."""
    return random.randint(40, 98)


def _generate_revenue_potential(trend_score: int) -> str:
    """Generate revenue potential based on trend score."""
    base = trend_score * random.randint(80, 150)
    variance = random.randint(-1000, 2000)
    total = max(500, base + variance)
    return f"${total:,}"


def _generate_opportunity_ratio() -> float:
    """Generate opportunity ratio (views vs competition)."""
    return round(random.uniform(0.5, 2.8), 2)


def _determine_competition_level(opportunity_ratio: float) -> str:
    """Determine competition level from opportunity ratio."""
    if opportunity_ratio > 1.8:
        return "low"
    elif opportunity_ratio > 1.2:
        return "medium"
    return "high"


def _assign_platforms() -> list[str]:
    """Assign platforms to a topic."""
    all_platforms = ["youtube", "tiktok", "instagram"]
    num_platforms = random.randint(1, 3)
    return random.sample(all_platforms, num_platforms)


# ─── Main Discovery Function ──────────────────────────────────────────────────

async def discover_topics(limit: int = 10, niche: str = "") -> list[dict]:
    """Discover trending topics with full metrics.

    Args:
        limit: Maximum number of topics to return
        niche: Optional niche filter

    Returns:
        List of topics with full metrics
    """
    # Get base topics from trending agent
    base_topics = await get_trending_topics(limit=limit * 2)

    # Enrich with metrics
    enriched = []
    for idx, topic in enumerate(base_topics[:limit]):
        trend_score = _generate_trend_score()
        opportunity_ratio = _generate_opportunity_ratio()

        enriched.append({
            "id": f"topic_{idx}_{int(datetime.now().timestamp())}",
            "title": topic.get("title", "Trending Topic"),
            "url": topic.get("url", ""),
            "thumbnail": topic.get("thumbnail", ""),
            "source": topic.get("source", "unknown"),
            # Full metrics
            "trend_score": trend_score,
            "revenue_potential": _generate_revenue_potential(trend_score),
            "opportunity_ratio": opportunity_ratio,
            "competition_level": _determine_competition_level(opportunity_ratio),
            "platforms": _assign_platforms(),
            # Metadata
            "discovered_at": datetime.now().isoformat(),
            "niche": niche or "general",
        })

    # Sort by trend_score descending
    enriched.sort(key=lambda x: x["trend_score"], reverse=True)

    return enriched


async def run_discovery(niche: str = "", platforms: list[str] | None = None) -> dict:
    """Run full discovery scan and broadcast via WebSocket.

    Args:
        niche: Optional niche filter
        platforms: Optional platform filter

    Returns:
        Discovery result with topics and metadata
    """
    from core.websocket_manager import manager

    await manager.log("Starting topic discovery scan...", "info")

    topics = await discover_topics(limit=10, niche=niche)

    await manager.log(f"Discovered {len(topics)} trending topics", "success")

    # Broadcast real-time update
    await manager.broadcast({
        "type": "topic_discovery",
        "topics": topics,
        "count": len(topics),
    })

    return {
        "status": "ok",
        "topics": topics,
        "count": len(topics),
        " niche": niche or "all",
        "timestamp": datetime.now().isoformat(),
    }