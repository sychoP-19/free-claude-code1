import random
import re
import json
from datetime import datetime
from pathlib import Path
from core.llm import llm_json
from core.downloader import download_video, DOWNLOADS_DIR
try:
    from skill_utils import web_search_exa
except ModuleNotFoundError:
    async def web_search_exa(query: str, **_):  # type: ignore[misc]
        return []

# Output directories
TOPICS_DIR = Path(__file__).parent.parent / "outputs" / "topics"
TOPICS_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = "You are a trend analyst. Return ONLY valid JSON, no explanation."


async def run(query: str, platform: str, window: str, output_batch: bool = True) -> dict:
    """Mine trending topics using LLM (proxy → Ollama → offline fallback)."""
    search_results = await web_search_exa(query=f"trending {query} {platform} {window}", numResults=10)

    prompt = f"""Analyze trends for niche: "{query}" on {platform} over {window}.
Search hints: {json.dumps(search_results)[:1000]}

Return JSON with exactly 10 topics:
{{
  "batch_id": "batch_{datetime.now().strftime('%Y%m%d')}",
  "query": "{query}",
  "platform": "{platform}",
  "window": "{window}",
  "generated_at": "{datetime.now().isoformat()}",
  "topics": [
    {{
      "id": "topic_001",
      "title": "topic title here",
      "platform": "{platform}",
      "trend_score": 88,
      "velocity": "rising",
      "competition": "Medium",
      "saturation": 45,
      "estimated_cpm": 6.5,
      "hashtags": ["#tag1", "#tag2"],
      "peak_window": "3-5 days"
    }}
  ],
  "summary": {{
    "total_topics": 10,
    "avg_trend_score": 72,
    "competition_level": "Medium",
    "best_opportunity": "topic_001"
  }}
}}"""

    result = await llm_json(prompt, system=SYSTEM_PROMPT)

    if not result or not result.get("topics"):
        result = _fallback(query, platform)

    if output_batch:
        batch_id = result.setdefault("batch_id", f"batch_{datetime.now().strftime('%Y%m%d')}")
        output_path = TOPICS_DIR / f"{batch_id}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        result["_output_path"] = str(output_path)

    return result


async def generate_blueprint(topic_id: str, topic_data: dict) -> dict:
    """Generate a script blueprint from a selected topic."""
    from core.llm import llm_complete
    title = topic_data.get("title", "trending topic")
    prompt = f"""Write a viral 60-second short-form video script for: "{title}"

HOOK (0-3s): [attention grabber]
BODY (3-45s): [3 key points, punchy]
CTA (45-60s): [strong call to action]

Keep it viral and monetization-ready."""
    script = await llm_complete(prompt) or _fallback_script(title)
    return {"script": script, "topic_id": topic_id}


async def download(url: str) -> dict:
    return await download_video(url, DOWNLOADS_DIR)


def _fallback(query: str, platform: str) -> dict:
    """Fallback generator when Ollama fails - returns 10 topics with structured metrics."""
    velocities = ["explosive", "rising", "stable", "emerging", "rising", "stable", "explosive", "emerging", "rising", "stable"]
    competitions = ["Low", "Medium", "High", "Medium", "Low", "High", "Medium", "Low", "Medium", "High"]
    saturations = [22, 45, 78, 55, 18, 82, 38, 12, 48, 68]
    scores = [94, 78, 52, 65, 88, 48, 82, 71, 59, 44]
    peak_windows = ["1-2 days", "3-5 days", "evergreen", "5-7 days", "1-2 weeks", "evergreen", "2-3 days", "1-2 days", "5-7 days", "evergreen"]

    base_titles = [
        f"Why Everyone Is Talking About {query}",
        f"The {query} Secret Nobody Tells You",
        f"I Tried {query} For 30 Days — Results",
        f"{query} Hack That Actually Works",
        f"Stop Doing {query} Wrong — Do This Instead",
        f"{query} Mistakes Everyone Makes",
        f"The Future of {query} in 2026",
        f"{query} Before vs After (Shocking)",
        f"Top 5 {query} Tips for Beginners",
        f"Expert Reacts to {query} Trends",
    ]

    topics = []
    for i in range(10):
        topics.append({
            "id": f"topic_{i+1:03d}",
            "title": base_titles[i],
            "platform": platform,
            "trend_score": scores[i],
            "velocity": velocities[i],
            "competition": competitions[i],
            "saturation": saturations[i],
            "estimated_cpm": round(random.uniform(2.5, 12.0), 2),
            "hashtags": [f"#{query.replace(' ', '')}", "#viral", "#trending", "#fyp", "#shorts"],
            "peak_window": peak_windows[i],
        })

    return {
        "batch_id": f"batch_{datetime.now().strftime('%Y%m%d')}",
        "query": query,
        "platform": platform,
        "window": "7 days",
        "generated_at": datetime.now().isoformat(),
        "topics": topics,
        "summary": {
            "total_topics": 10,
            "avg_trend_score": round(sum(scores) / len(scores), 1),
            "competition_level": "Medium",
            "best_opportunity": "topic_005" if scores[4] == max(scores) else "topic_001",
        },
    }


def _fallback_script(title: str) -> str:
    return f"""HOOK (0-3s):
"Stop scrolling. This changed everything about {title}."

BODY (3-45s):
Point 1: Most people don't know the #1 mistake with {title}.
Point 2: Here's what the top 1% actually do differently.
Point 3: In just 7 days, this simple shift can transform your results.

CTA (45-60s):
"Follow for more secrets like this. Link in bio to go deeper."
"""
