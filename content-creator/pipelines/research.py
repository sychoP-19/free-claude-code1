"""pipelines/research.py — auto research brief from RSS + Ollama."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import httpx

from pipelines.base import PipelineRun, OUTPUTS, build_system_prompt, slugify
from pipelines.llm import chat
from core.web_intel import search_trending, scrape_article


SEARCH_FEEDS = [
    "https://hnrss.org/newest?q={q}",
    "https://www.reddit.com/search.rss?q={q}&sort=new",
]


class ResearchPipeline(PipelineRun):
    pipeline = "research"
    publish_platforms = ()  # Briefs aren't published

    async def execute(self) -> tuple[str, dict]:
        topic = self.params.get("topic", "").strip()
        if not topic:
            raise ValueError("topic is required")

        slug = slugify(topic)
        out_dir = OUTPUTS / "research" / slug
        out_dir.mkdir(parents=True, exist_ok=True)

        await self.set_stage("research", 10)
        await self.emit("researcher", "act", f"Fetching trending data for '{topic}'")
        trending = await search_trending(topic)
        await self.emit("researcher", "done", f"{len(trending)} trending items found")

        await self.set_stage("research", 20)
        await self.emit("researcher", "act", f"Scraping sources for '{topic}'")
        sources = await self._fetch_sources(topic)

        # Enrich sources with real trending data
        for item in trending[:5]:
            sources.insert(0, {
                "title": item["title"],
                "link": item.get("url", ""),
                "summary": f"[Trending • score {item.get('score', 0)} • {item.get('source', '')}]",
            })

        # Scrape the top trending article for deeper context
        top_url = next((t["url"] for t in trending if t.get("url", "").startswith("http")), None)
        scraped_body = ""
        if top_url:
            try:
                await self.emit("researcher", "act", f"Scraping top result: {top_url[:60]}")
                article = await scrape_article(top_url)
                scraped_body = article.get("body", "")[:1000]
                if scraped_body:
                    await self.emit("researcher", "done", "Article scraped successfully")
            except Exception:
                pass

        await self.emit("researcher", "done", f"{len(sources)} total sources gathered")
        sources = [*sources, *([{"title": "Scraped content", "link": top_url or "", "summary": scraped_body}] if scraped_body else [])]

        await self.set_stage("script", 60)
        await self.emit("strategist", "act", "Synthesizing brief")
        brief = await self._synthesize(topic, sources)

        await self.set_stage("assembly", 90)
        path = out_dir / "brief.md"
        path.write_text(brief, encoding="utf-8")
        self.track_asset("text", str(path), caption=topic, tags=["research", slug])

        await self.set_stage("assembly", 100)
        return str(path), {"slug": slug, "sources": len(sources), "out_dir": str(out_dir)}

    async def _fetch_sources(self, topic: str) -> list[dict]:
        import feedparser
        urls = [f.format(q=topic.replace(" ", "+")) for f in SEARCH_FEEDS]
        results: list[dict] = []
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            for url in urls:
                try:
                    r = await client.get(url, headers={"User-Agent": "JARVIS/1.0"})
                    feed = feedparser.parse(r.text)
                    for e in feed.entries[:10]:
                        results.append({
                            "title": e.get("title", ""),
                            "link":  e.get("link", ""),
                            "summary": (e.get("summary", "") or "")[:400],
                        })
                except Exception:
                    continue
        return results

    async def _synthesize(self, topic: str, sources: list[dict]) -> str:
        bullets = "\n".join(f"- {s['title']} — {s['summary'][:160]}" for s in sources[:30])
        prompt = (
            f"Synthesize a research brief on: {topic}.\n"
            f"Sources:\n{bullets}\n\n"
            f"Output Markdown with: Executive Summary (3 bullets), Key Findings (5-8 bullets), "
            f"Angles for Content (5 specific topic ideas), and Open Questions."
        )
        try:
            return await chat(
                [{"role": "user", "content": prompt}],
                system=build_system_prompt("researcher"),
                max_tokens=1500, run_id=self.run_id,
            )
        except Exception as e:
            return f"# Research brief: {topic}\n\nLLM unavailable: {e}\n\n## Sources\n\n{bullets}\n"


async def run(params: dict) -> dict:
    res = await ResearchPipeline(params).run()
    return res.__dict__
