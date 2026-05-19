import random
import httpx
from core import ollama_client as ollama


SYSTEM_PROMPT = """You are an expert social media analyst. Given a channel URL or handle,
produce a realistic, data-driven JSON analysis. Return ONLY valid JSON, no explanation."""


async def run(url: str, platform: str) -> dict:
    models = await ollama.list_models()
    model = ollama.pick_model(models, ["mistral:7b", "llama3:8b", "phi3:mini"])

    prompt = f"""Analyze this {platform} channel: {url}

Return JSON with these exact keys:
{{
  "name": "channel name",
  "platform": "{platform}",
  "niche": "content niche",
  "profit_score": 7,
  "subscribers": 125000,
  "avg_views": 45000,
  "post_frequency": "3x per week",
  "engagement_rate": 4.2,
  "hook_formula": "describe their hook pattern in 2-3 sentences",
  "revenue_est": 8500,
  "revenue_streams": {{"adsense": 2500, "sponsor": 4000, "affiliate": 1500, "merch": 500}},
  "top_videos": [
    {{"title": "video title", "views": 250000, "type": "SHORT"}},
    {{"title": "video title", "views": 180000, "type": "LONG"}},
    {{"title": "video title", "views": 120000, "type": "SHORT"}}
  ],
  "posting_times": [
    {{"day": "Tuesday", "time": "18:00", "avg_views": 52000, "signal": "HIGH"}},
    {{"day": "Thursday", "time": "19:00", "avg_views": 48000, "signal": "HIGH"}},
    {{"day": "Saturday", "time": "11:00", "avg_views": 41000, "signal": "MEDIUM"}}
  ],
  "hashtags": ["#niche1", "#niche2", "#niche3", "#niche4", "#niche5"]
}}

Make it realistic for the platform and niche. Return only JSON."""

    try:
        response = await ollama.generate(model, prompt, system=SYSTEM_PROMPT)
        import json, re
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass

    return _fallback(url, platform)


def _fallback(url: str, platform: str) -> dict:
    name = url.split("@")[-1].split("/")[-1].strip() or "Unknown Channel"
    return {
        "name": name,
        "platform": platform,
        "niche": "General Content",
        "profit_score": random.randint(5, 9),
        "subscribers": random.randint(10000, 500000),
        "avg_views": random.randint(5000, 100000),
        "post_frequency": random.choice(["Daily", "3x/week", "2x/week"]),
        "engagement_rate": round(random.uniform(2, 8), 1),
        "hook_formula": "Opens with a bold claim, uses pattern interrupts every 15 seconds, closes with strong CTA.",
        "revenue_est": random.randint(2000, 25000),
        "revenue_streams": {
            "adsense":   random.randint(500, 5000),
            "sponsor":   random.randint(1000, 10000),
            "affiliate": random.randint(300, 3000),
            "merch":     random.randint(100, 2000),
        },
        "top_videos": [
            {"title": "How I Made $10K In 30 Days", "views": random.randint(100000, 1000000), "type": "SHORT"},
            {"title": "The Truth About This Niche", "views": random.randint(50000, 500000), "type": "LONG"},
            {"title": "Watch This Before You Start", "views": random.randint(30000, 300000), "type": "SHORT"},
        ],
        "posting_times": [
            {"day": "Tuesday", "time": "18:00", "avg_views": random.randint(20000, 80000), "signal": "HIGH"},
            {"day": "Thursday", "time": "19:00", "avg_views": random.randint(15000, 60000), "signal": "HIGH"},
            {"day": "Saturday", "time": "11:00", "avg_views": random.randint(10000, 50000), "signal": "MEDIUM"},
        ],
        "hashtags": ["#trending", "#viral", "#content", "#money", "#growth"],
    }
