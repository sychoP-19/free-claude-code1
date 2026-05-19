"""pipelines/blog.py — 1500-word article + hero image + meta JSON.

Includes:
  BlogPipeline        – original blog post generator
  generate_twitter_thread() – 10-tweet thread, hook-first, ≤280 chars each
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

from pipelines.base import PipelineRun, OUTPUTS, build_system_prompt, slugify
from pipelines.llm import chat


class BlogPipeline(PipelineRun):
    pipeline = "blog"
    publish_platforms = ("medium", "hashnode")

    async def execute(self) -> tuple[str, dict]:
        topic = self.params.get("topic", "").strip()
        words = int(self.params.get("words", 1500))
        if not topic:
            raise ValueError("topic is required")

        slug = slugify(topic)
        out_dir = OUTPUTS / "blog" / slug
        out_dir.mkdir(parents=True, exist_ok=True)

        await self.set_stage("script", 20)
        await self.emit("writer", "act", f"Writing {words}-word article on '{topic}'")
        article = await self._article(topic, words)

        await self.set_stage("visuals", 60)
        await self.emit("designer", "act", "Generating hero image")
        hero = out_dir / "hero.jpg"
        async with httpx.AsyncClient(timeout=120) as client:
            ok = await self._pollinations(client, topic, hero, w=1600, h=900)
        if not ok:
            await self.emit("designer", "error", "Hero image failed; continuing without")

        await self.set_stage("assembly", 90)
        post = out_dir / "post.md"
        title = self._extract_title(article, topic)
        post.write_text(article, encoding="utf-8")

        meta = out_dir / "meta.json"
        meta_data = {
            "title": title,
            "slug": slug,
            "topic": topic,
            "word_count": len(article.split()),
            "hero": "hero.jpg" if hero.exists() else "",
            "platforms": list(self.publish_platforms),
        }
        meta.write_text(json.dumps(meta_data, indent=2), encoding="utf-8")

        self.track_asset("text",  str(post), caption=title, tags=["blog", slug])
        self.track_asset("text",  str(meta), caption="meta", tags=["meta", slug])
        if hero.exists():
            self.track_asset("image", str(hero), caption=title, tags=["hero", slug])

        await self.set_stage("assembly", 100)
        return str(post), {"slug": slug, "words": meta_data["word_count"], "out_dir": str(out_dir)}

    async def _article(self, topic: str, words: int) -> str:
        prompt = (
            f"Write a {words}-word article on: {topic}.\n"
            f"Use Markdown: H1 title, then H2/H3 subheads. Include 4-6 sections. "
            f"Conversational but authoritative. No hashtags. End with a 'Key Takeaways' bullet list."
        )
        return await chat(
            [{"role": "user", "content": prompt}],
            system=build_system_prompt("writer"),
            max_tokens=4000, run_id=self.run_id,
        )

    async def _pollinations(self, client: httpx.AsyncClient, prompt: str, dest: Path, w: int, h: int) -> bool:
        safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in prompt[:120]).replace(" ", "%20")
        url = (
            f"https://image.pollinations.ai/prompt/{safe}"
            f"?model=flux&width={w}&height={h}&seed={hash(prompt) % 99999}&nologo=true&enhance=true"
        )
        try:
            r = await client.get(url, follow_redirects=True, timeout=120)
            if r.status_code == 200 and len(r.content) > 5000:
                dest.write_bytes(r.content)
                return True
        except Exception:
            pass
        return False

    def _extract_title(self, md: str, fallback: str) -> str:
        for line in md.splitlines():
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
        return fallback


async def run(params: dict) -> dict:
    res = await BlogPipeline(params).run()
    return res.__dict__


# ─────────────────────────────────────────────────────────────────────────────
# Twitter / X Thread generator — 10 numbered tweets, hook-first, ≤280 chars
# ─────────────────────────────────────────────────────────────────────────────

async def generate_twitter_thread(topic: str) -> dict:
    """
    Generate a 10-tweet thread on *topic*.

    Output file: outputs/blog/<slug>/thread.txt

    Returns:
        {
          "ok": True,
          "slug": str,
          "path": str,          # absolute path to thread.txt
          "tweets": [str, ...], # list of 10 tweet strings (numbered)
          "char_counts": [int, ...],
        }
    """
    slug = slugify(topic)
    out_dir = OUTPUTS / "blog" / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    prompt = (
        f"Write a 10-tweet Twitter thread on: {topic}.\n"
        f"Rules:\n"
        f"- Tweet 1 is a powerful hook (question, bold claim, or surprising stat). "
        f"Start it WITHOUT '1/' — just the hook text.\n"
        f"- Tweets 2-9 build the story/value; each is self-contained.\n"
        f"- Tweet 10 is a recap + CTA (follow, save, share).\n"
        f"- Every tweet ≤ 260 chars (leave room for numbering).\n"
        f"- No hashtags in the middle. You may add 2-3 hashtags to tweet 10 only.\n"
        f"- Use line breaks inside tweets for readability (\\n).\n"
        f"Return a JSON array of exactly 10 strings."
    )

    tweets: list[str] = []
    try:
        reply = await chat(
            [{"role": "user", "content": prompt}],
            system=build_system_prompt("writer"),
            max_tokens=1600,
        )
        m = re.search(r"\[.*\]", reply, re.DOTALL)
        if m:
            arr = json.loads(m.group())
            tweets = [str(t).strip() for t in arr if str(t).strip()]
    except Exception:
        pass

    if len(tweets) < 8:
        # Fallback: split any paragraph reply into ~10 chunks
        lines = [l.strip() for l in reply.splitlines() if l.strip()] if "reply" in dir() else []
        tweets = lines[:10] if lines else [f"Tweet {i+1} about {topic}" for i in range(10)]

    # Trim to 10 and add "N/" prefix
    tweets = tweets[:10]
    numbered: list[str] = []
    for i, t in enumerate(tweets):
        prefix = f"{i+1}/"
        body = t.lstrip("0123456789/").strip()
        full = f"{prefix} {body}"
        # Hard-truncate at 280 chars (rare edge case)
        if len(full) > 280:
            full = full[:277] + "…"
        numbered.append(full)

    # Write thread.txt — blank line between tweets for readability
    thread_path = out_dir / "thread.txt"
    thread_path.write_text("\n\n".join(numbered), encoding="utf-8")

    if thread_path.stat().st_size == 0:
        raise RuntimeError("thread.txt is empty")

    return {
        "ok": True,
        "slug": slug,
        "path": str(thread_path),
        "tweets": numbered,
        "char_counts": [len(t) for t in numbered],
    }


