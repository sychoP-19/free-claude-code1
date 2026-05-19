"""core/web_intel.py — Lightweight web research using httpx + BeautifulSoup.

No Playwright/Selenium. Uses realistic browser headers to avoid simple blocks.
Patterns adapted from CloakBrowser's fingerprint/UA approach (realistic Windows
Chrome profile, randomised seed per session).
"""
from __future__ import annotations

import logging
import random
import re
from urllib.parse import quote_plus

import httpx

log = logging.getLogger("jarvis.web_intel")

# ---------------------------------------------------------------------------
# Realistic browser headers (Windows Chrome 124 — mirrors CloakBrowser's
# default fingerprint profile for Windows x64)
# ---------------------------------------------------------------------------
_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


def _headers(referer: str = "https://www.google.com/") -> dict[str, str]:
    return {
        "User-Agent": random.choice(_UAS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": referer,
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
    }


def _reddit_headers() -> dict[str, str]:
    """Reddit prefers a descriptive bot UA when using the JSON API."""
    return {
        "User-Agent": "JARVIS-ContentResearch/1.0 (research bot; contact admin@jarvis.local)",
        "Accept": "application/json",
    }


_TIMEOUT = httpx.Timeout(15.0, connect=8.0)


# ---------------------------------------------------------------------------
# Google Trends RSS → niche trending topics
# ---------------------------------------------------------------------------
async def search_trending(niche: str) -> list[dict]:
    """Return trending topics for a niche.

    Tries Google Trends RSS first, falls back to Reddit /r/<niche>/hot.

    Returns: [{"title": str, "url": str, "score": int}]
    """
    results: list[dict] = []

    # 1) Google Trends RSS (geo=US, no auth needed)
    try:
        trends_url = f"https://trends.google.com/trending/rss?geo=US&q={quote_plus(niche)}"
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
            r = await client.get(trends_url, headers=_headers("https://trends.google.com/"))
            if r.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(r.text)
                ns = {"ht": "https://trends.google.com/trending/rss"}
                for item in root.findall(".//item"):
                    title_el = item.find("title")
                    link_el = item.find("link")
                    traffic_el = item.find("ht:approx_traffic", ns)
                    if title_el is None:
                        continue
                    traffic_raw = (traffic_el.text or "0") if traffic_el is not None else "0"
                    score = int(re.sub(r"[^\d]", "", traffic_raw) or "0")
                    results.append({
                        "title": title_el.text or "",
                        "url": link_el.text if link_el is not None else "",
                        "score": score,
                        "source": "google_trends",
                    })
    except Exception as e:
        log.debug("Google Trends RSS failed: %s", e)

    # 2) Reddit /r/<niche>/hot fallback (or supplement)
    if len(results) < 5:
        subreddit = niche.lower().replace(" ", "")
        try:
            reddit_url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=25"
            async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
                r = await client.get(reddit_url, headers=_reddit_headers())
                if r.status_code == 200:
                    data = r.json()
                    for post in data.get("data", {}).get("children", []):
                        p = post.get("data", {})
                        if p.get("stickied"):
                            continue
                        results.append({
                            "title": p.get("title", ""),
                            "url": f"https://reddit.com{p.get('permalink', '')}",
                            "score": p.get("score", 0),
                            "source": "reddit",
                        })
        except Exception as e:
            log.debug("Reddit fallback failed for r/%s: %s", subreddit, e)

    # 3) General search-ish Reddit fallback if subreddit didn't exist
    if len(results) < 3:
        try:
            search_url = f"https://www.reddit.com/search.json?q={quote_plus(niche)}&sort=hot&limit=20"
            async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
                r = await client.get(search_url, headers=_reddit_headers())
                if r.status_code == 200:
                    data = r.json()
                    for post in data.get("data", {}).get("children", []):
                        p = post.get("data", {})
                        results.append({
                            "title": p.get("title", ""),
                            "url": f"https://reddit.com{p.get('permalink', '')}",
                            "score": p.get("score", 0),
                            "source": "reddit_search",
                        })
        except Exception as e:
            log.debug("Reddit search fallback failed: %s", e)

    # deduplicate by title, sort by score desc
    seen: set[str] = set()
    unique: list[dict] = []
    for r in sorted(results, key=lambda x: x["score"], reverse=True):
        key = r["title"].lower()[:60]
        if key and key not in seen:
            seen.add(key)
            unique.append(r)

    return unique[:20]


# ---------------------------------------------------------------------------
# Article scraper
# ---------------------------------------------------------------------------
async def scrape_article(url: str) -> dict:
    """Fetch and extract readable text from an article URL.

    Returns: {"title": str, "body": str, "author": str, "date": str, "url": str}
    """
    default = {"title": "", "body": "", "author": "", "date": "", "url": url}
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        log.warning("beautifulsoup4 not installed — scrape_article unavailable")
        return {**default, "body": "beautifulsoup4 not installed"}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
            r = await client.get(url, headers=_headers(url))
            if r.status_code != 200:
                return {**default, "body": f"HTTP {r.status_code}"}
            soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        log.debug("scrape_article fetch error for %s: %s", url, e)
        return {**default, "body": f"Fetch error: {e}"}

    # Title
    title = ""
    if soup.find("h1"):
        title = soup.find("h1").get_text(strip=True)
    elif soup.title:
        title = soup.title.get_text(strip=True)

    # Author
    author = ""
    for sel in ['[rel="author"]', '.author', '[itemprop="author"]', '.byline']:
        el = soup.select_one(sel)
        if el:
            author = el.get_text(strip=True)[:100]
            break

    # Date
    date = ""
    for sel in ["time", '[itemprop="datePublished"]', ".date", ".published"]:
        el = soup.select_one(sel)
        if el:
            date = el.get("datetime") or el.get_text(strip=True)
            date = date[:30]
            break

    # Body — try article tag, then main, then biggest <div> by word count
    body = ""
    for tag in ["article", "main", '[role="main"]']:
        el = soup.select_one(tag)
        if el:
            body = el.get_text(separator=" ", strip=True)
            break

    if not body:
        # Pick the div with the most text
        best, best_len = None, 0
        for div in soup.find_all("div"):
            t = div.get_text(separator=" ", strip=True)
            if len(t) > best_len:
                best, best_len = div, len(t)
        if best:
            body = best.get_text(separator=" ", strip=True)

    # Clean whitespace, cap at 4000 chars
    body = re.sub(r"\s{2,}", " ", body)[:4000]

    return {"title": title, "body": body, "author": author, "date": date, "url": url}


# ---------------------------------------------------------------------------
# Viral hook finder via Reddit title analysis
# ---------------------------------------------------------------------------
async def find_viral_hooks(topic: str) -> list[str]:
    """Find viral hook phrases by analysing high-upvote Reddit post titles.

    Returns top 5 hook-style titles.
    """
    hooks: list[tuple[int, str]] = []

    try:
        search_url = f"https://www.reddit.com/search.json?q={quote_plus(topic)}&sort=top&t=month&limit=50"
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
            r = await client.get(search_url, headers=_reddit_headers())
            if r.status_code == 200:
                data = r.json()
                for post in data.get("data", {}).get("children", []):
                    p = post.get("data", {})
                    title = p.get("title", "").strip()
                    score = p.get("score", 0)
                    if title and score > 10:
                        hooks.append((score, title))
    except Exception as e:
        log.debug("find_viral_hooks Reddit search failed: %s", e)

    # Also try Hacker News Algolia search
    try:
        hn_url = f"https://hn.algolia.com/api/v1/search?query={quote_plus(topic)}&tags=story&hitsPerPage=30"
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
            r = await client.get(hn_url, headers={"User-Agent": _UAS[0]})
            if r.status_code == 200:
                data = r.json()
                for hit in data.get("hits", []):
                    title = (hit.get("title") or "").strip()
                    score = hit.get("points") or 0
                    if title and score > 5:
                        hooks.append((score, title))
    except Exception as e:
        log.debug("find_viral_hooks HN failed: %s", e)

    if not hooks:
        return []

    hooks.sort(key=lambda x: x[0], reverse=True)
    seen: set[str] = set()
    result: list[str] = []
    for _, title in hooks:
        key = title.lower()[:50]
        if key not in seen:
            seen.add(key)
            result.append(title)
        if len(result) >= 5:
            break
    return result


# ---------------------------------------------------------------------------
# YouTube trending via RSS (no API key needed)
# ---------------------------------------------------------------------------
async def get_youtube_trends() -> list[dict]:
    """Get trending YouTube-related content without an API key.

    YouTube's chart=most_popular RSS was deprecated. This function:
    1. Searches Reddit r/videos and r/youtube for top posts (real video links).
    2. Falls back to HN Algolia search for "youtube" stories with video URLs.

    Returns: [{"title": str, "video_id": str, "published": str, "url": str}]
    """
    results: list[dict] = []

    # 1) Reddit r/videos hot posts — contain real YouTube links
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
            r = await client.get(
                "https://www.reddit.com/r/videos/hot.json?limit=25",
                headers=_reddit_headers(),
            )
            if r.status_code == 200:
                data = r.json()
                for post in data.get("data", {}).get("children", []):
                    p = post.get("data", {})
                    if p.get("stickied"):
                        continue
                    url = p.get("url", "")
                    # extract youtube video id
                    video_id = ""
                    for pat in ["v=", "youtu.be/"]:
                        if pat in url:
                            raw = url.split(pat)[-1]
                            video_id = raw[:11]
                            break
                    results.append({
                        "title": p.get("title", ""),
                        "video_id": video_id,
                        "published": "",
                        "url": url or f"https://www.youtube.com/watch?v={video_id}",
                        "score": p.get("score", 0),
                        "source": "reddit_videos",
                    })
    except Exception as e:
        log.debug("get_youtube_trends reddit failed: %s", e)

    # 2) Reddit r/youtube hot posts as supplement
    if len(results) < 5:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
                r = await client.get(
                    "https://www.reddit.com/r/youtube/hot.json?limit=15",
                    headers=_reddit_headers(),
                )
                if r.status_code == 200:
                    data = r.json()
                    for post in data.get("data", {}).get("children", []):
                        p = post.get("data", {})
                        if p.get("stickied"):
                            continue
                        results.append({
                            "title": p.get("title", ""),
                            "video_id": "",
                            "published": "",
                            "url": f"https://reddit.com{p.get('permalink', '')}",
                            "score": p.get("score", 0),
                            "source": "reddit_youtube",
                        })
        except Exception as e:
            log.debug("get_youtube_trends r/youtube failed: %s", e)

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results[:10]
