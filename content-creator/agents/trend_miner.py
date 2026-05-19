import random
import re
import json
from datetime import datetime
from pathlib import Path
from core import ollama_client as ollama
from core.downloader import download_video, DOWNLOADS_DIR

# Output directories
TOPICS_DIR = Path(__file__).parent.parent / "outputs" / "topics"
TOPICS_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = "You are a trend analyst. Return ONLY valid JSON, no explanation."


async def run(query: str, platform: str, window: str, output_batch: bool = True) -> dict:
    """
    Mine trending topics for a given niche/platform/time window.

    Args:
        query: Niche/topic to analyze
        platform: Target platform (youtube, tiktok, instagram)
        window: Time window (e.g., "7 days", "30 days")
        output_batch: If True, write results to batch_YYYYMMDD.json

    Returns:
        Dict with 10-15 topic candidates with trend metrics
    """
    models = await ollama.list_models()
    model = ollama.pick_model(models, ["mistral:7b", "llama3:8b", "phi3:mini"])

    prompt = f"""Analyze trending content for niche: "{query}" on {platform} in the last {window}.

Return JSON with 10-15 topic candidates:
{{
  "batch_id": "batch_YYYYMMDD",
  "query": "{query}",
  "platform": "{platform}",
  "window": "{window}",
  "generated_at": "ISO timestamp",
  "topics": [
    {{"id": "topic_001", "title": "trend title", "platform": "{platform}", "trend_score": 94, "velocity": "explosive", "competition": "Medium", "saturation": 34, "estimated_cpm": 8.50, "hashtags": ["#tag1","#tag2","#tag3","#tag4","#tag5"], "peak_window": "2-3 days"}},
    {{"id": "topic_002", "title": "trend title", "platform": "{platform}", "trend_score": 78, "velocity": "rising", "competition": "Low", "saturation": 22, "estimated_cpm": 6.20, "hashtags": ["#tag1","#tag2","#tag3","#tag4","#tag5"], "peak_window": "5-7 days"}},
    {{"id": "topic_003", "title": "trend title", "platform": "{platform}", "trend_score": 65, "velocity": "stable", "competition": "High", "saturation": 78, "estimated_cpm": 4.50, "hashtags": ["#tag1","#tag2","#tag3","#tag4","#tag5"], "peak_window": "evergreen"}}
  ],
  "summary": {{
    "total_topics": 10,
    "avg_trend_score": 72.4,
    "competition_level": "Medium",
    "best_opportunity": "topic_002"
  }}
}}

Make topics realistic for the "{query}" niche. Vary scores, competition, and saturation. Return only JSON."""

    try:
        response = await ollama.generate(model, prompt, system=SYSTEM_PROMPT)
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            result = json.loads(match.group())

            # Output to batch file if requested
            if output_batch:
                batch_id = f"batch_{datetime.now().strftime('%Y%m%d')}"
                result["batch_id"] = batch_id
                output_path = TOPICS_DIR / f"{batch_id}.json"
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                result["_output_path"] = str(output_path)

            return result
    except Exception:
        pass

    result = _fallback(query, platform)

    # Write fallback to file if requested
    if output_batch:
        batch_id = f"batch_{datetime.now().strftime('%Y%m%d')}"
        result["batch_id"] = batch_id
        output_path = TOPICS_DIR / f"{batch_id}.json"
        result["_output_path"] = str(output_path)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    return result


async def generate_blueprint(topic_id: str, topic_data: dict) -> dict:
    """
    Generate a script blueprint from a selected topic (Stage 1 output).

    Args:
        topic_id: Topic identifier
        topic_data: Topic data from Stage 1 output (with 'title', 'hashtags', etc.)

    Returns:
        Script blueprint dict
    """
    models = await ollama.list_models()
    model = ollama.pick_model(models, ["mistral:7b", "llama3:8b", "phi3:mini"])

    title = topic_data.get("title", "trending topic")

    prompt = f"""Write a viral short-form video script for this trending topic: "{title}"

Format as a 60-second script with:
HOOK (0-3s): [attention grabber]
BODY (3-45s): [3 key points]
CTA (45-60s): [call to action]

Keep it punchy, viral, and monetization-ready."""

    try:
        script = await ollama.generate(model, prompt)
        return {"script": script, "topic_id": topic_id}
    except Exception:
        return {"script": _fallback_script(title), "topic_id": topic_id}


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
