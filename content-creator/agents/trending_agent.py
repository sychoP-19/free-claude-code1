"""trending_agent.py — YouTube RSS trending topics (free, no key)."""
import asyncio
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx

_RSS_URL = "https://www.youtube.com/feeds/videos.xml?chart=mostpopular&hl=en&gl=US"
_NS = {"atom": "http://www.w3.org/2005/Atom", "media": "http://search.yahoo.com/mrss/"}

_FALLBACK = [
    "AI coding tools 2025", "YouTube Shorts monetization tips", "Viral content strategy",
    "ChatGPT vs Claude comparison", "Passive income with AI", "Python automation tricks",
    "Midjourney vs Stable Diffusion", "How to grow on YouTube fast", "Web scraping tutorial",
    "Machine learning for beginners", "Build a SaaS in a weekend", "Crypto bull run 2025",
    "Remote work productivity hacks", "Best AI image generators", "TikTok algorithm secrets",
    "Freelancing with AI tools", "YouTube automation channel", "Digital nomad lifestyle",
    "Stock market AI trading", "Prompt engineering masterclass",
]


async def get_trending_topics(limit: int = 20) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            r = await client.get(_RSS_URL)
            r.raise_for_status()
        return _parse_feed(r.text, limit)
    except Exception:
        return _fallback_topics(limit)


def _parse_feed(xml_text: str, limit: int) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return _fallback_topics(limit)

    topics = []
    for entry in root.findall("atom:entry", _NS)[:limit]:
        title_el = entry.find("atom:title", _NS)
        link_el  = entry.find("atom:link", _NS)
        thumb_el = entry.find("media:group/media:thumbnail", _NS)
        title = title_el.text if title_el is not None else "Trending Video"
        url   = link_el.get("href", "") if link_el is not None else ""
        thumb = thumb_el.get("url", "") if thumb_el is not None else ""
        topics.append({"title": title, "url": url, "thumbnail": thumb, "source": "youtube_rss"})

    return topics if topics else _fallback_topics(limit)


def _fallback_topics(limit: int) -> list[dict]:
    return [
        {"title": t, "url": "", "thumbnail": "", "source": "fallback"}
        for t in _FALLBACK[:limit]
    ]
