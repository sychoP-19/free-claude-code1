import json
from datetime import datetime
from pathlib import Path
from core.llm import llm_json
from agents.competitor_analyzer import CompetitorAnalyzer

SCRIPTS_DIR = Path(__file__).parent.parent / "outputs" / "scripts"
SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = "You are an expert viral content creator. Return ONLY valid JSON."

STYLE_NOTES = {
    "shorts":   "YouTube Shorts (60s max, hook in first 3s, fast cuts)",
    "tiktok":   "TikTok (15-30s, trending audio, text overlays)",
    "reel":     "Instagram Reel (15-30s, aesthetic, trending audio)",
    "longform": "Long-form YouTube (5-10min, chapters, SEO optimized)",
}

TONE_NOTES = {
    "viral":    "extremely catchy, controversial, pattern-interrupting",
    "edu":      "educational but entertaining, simplify complex topics",
    "story":    "personal story, emotional, relatable struggles",
    "listicle": "numbered list, each point builds on the last",
}


class ContentFactory:
    def __init__(self):
        self.analyzer = CompetitorAnalyzer()

    async def run(self, topic: str, style: str, tone: str, gen_script: bool = True,
                  gen_thumbnail: bool = True, gen_hashtags: bool = True,
                  topic_id: str = None, output_file: bool = True, arbitrage: bool = False) -> dict:
        """Generate a complete content package (proxy → Ollama → offline fallback)."""
        arbitrage_context = ""
        if arbitrage:
            intel = await self.analyzer.analyze_velocity(topic, ["youtube", "tiktok"])
            arbitrage_context = f"\nCompetitor Intel: {json.dumps(intel)[:500]}"

        style_desc = STYLE_NOTES.get(style, style)
        tone_desc = TONE_NOTES.get(tone, tone)

        prompt = f"""Create a 60-second viral content package for: "{topic}"
{arbitrage_context}
Format: {style_desc} | Tone: {tone_desc}

Return JSON:
{{
  "topic_id": "{topic_id or 'manual'}",
  "topic": "{topic}",
  "style": "{style}",
  "tone": "{tone}",
  "duration_seconds": 60,
  "script": {{
    "hook": "0-3s attention grabber",
    "body": "3-45s main content with 3 key points",
    "cta": "45-60s call to action"
  }},
  "scenes": [
    {{"scene_number": 1, "description": "visual", "timing": "0-10s", "text_overlay": "text"}},
    {{"scene_number": 2, "description": "visual", "timing": "10-25s", "text_overlay": "text"}},
    {{"scene_number": 3, "description": "visual", "timing": "25-40s", "text_overlay": "text"}},
    {{"scene_number": 4, "description": "visual", "timing": "40-50s", "text_overlay": "text"}},
    {{"scene_number": 5, "description": "visual", "timing": "50-60s", "text_overlay": "text"}}
  ],
  "hashtags": {{
    "youtube": ["#tag1","#tag2","#tag3","#tag4","#tag5"],
    "tiktok": ["#tag1","#tag2","#tag3","#tag4","#tag5"],
    "instagram": ["#tag1","#tag2","#tag3","#tag4","#tag5"]
  }},
  "thumbnail_prompts": [
    "cinematic close-up of {topic}, dramatic lighting, 8K",
    "minimalist flat design {topic} concept, bold typography",
    "person reacting to {topic}, shocked expression, studio lighting"
  ]
}}"""

        result = await llm_json(prompt, system=SYSTEM_PROMPT)
        if not result or not result.get("script"):
            result = _fallback(topic, style, tone, topic_id)

        if output_file:
            file_id = topic_id or f"script_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            output_path = SCRIPTS_DIR / f"{file_id}.json"
            result["_output_path"] = str(output_path)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

        return result


async def run(topic: str, style: str, tone: str, **kwargs) -> dict:
    return await ContentFactory().run(topic, style, tone, **kwargs)


def _fallback(topic: str, style: str, tone: str, topic_id: str = None) -> dict:
    """Fallback generator when Ollama fails - returns complete structured content package."""
    duration = {"shorts": 60, "tiktok": 28, "reel": 25, "longform": 480}.get(style, 60)

    return {
        "topic_id": topic_id or "fallback_manual",
        "topic": topic,
        "style": style,
        "tone": tone,
        "duration_seconds": duration,
        "script": {
            "hook": f"0-3s: Stop scrolling. This changed everything about {topic}.",
            "body": f"3-45s: Most people don't know the #1 mistake with {topic}. Here's what the top 1% actually do differently. In just 7 days, this simple shift can transform your results.",
            "cta": f"45-{duration}s: Follow for more secrets like this. Link in bio to go deeper.",
        },
        "scenes": [
            {"scene_number": 1, "description": "Close-up face, direct eye contact, hook line delivery", "timing": "0-8s", "text_overlay": f"STOP! {topic.upper()}"},
            {"scene_number": 2, "description": "Screen recording or B-roll showing common mistake", "timing": "8-18s", "text_overlay": "The #1 Mistake"},
            {"scene_number": 3, "description": "Split screen: wrong way vs right way", "timing": "18-28s", "text_overlay": "Wrong vs Right"},
            {"scene_number": 4, "description": "Demonstration of correct technique", "timing": "28-38s", "text_overlay": "The Pro Method"},
            {"scene_number": 5, "description": "Before/after results reveal", "timing": "38-48s", "text_overlay": "See the Difference"},
            {"scene_number": 6, "description": "Call to action with subscribe animation", "timing": f"48-{duration}s", "text_overlay": "Follow for More"},
        ],
        "hashtags": {
            "youtube": [f"#{topic.replace(' ', '')}", "#viral", "#trending", "#howto", "#tips", "#success", "#lifehack", "#fyp", "#shorts", "#tutorial"],
            "tiktok": [f"#{topic.replace(' ', '')}", "#fyp", "#foryou", "#viral", "#trending", "#tiktok", "#trend", "#explore", "#viralvideo", "#contentcreator"],
            "instagram": [f"#{topic.replace(' ', '')}", "#instagram", "#reels", "#reelsinstagram", "#viral", "#trending", "#explore", "#instagood", "#photooftheday", "#content"],
        },
        "thumbnail_prompts": [
            f"Bold red text '{topic.upper()}' on black background, shocked face expression, high contrast, cinematic lighting, 16:9 aspect ratio",
            f"Before/after split screen related to {topic}, arrow pointing right, bright colors, bold typography, high saturation",
            f"Clean white background, large emoji + '{topic}' in bold sans-serif, minimal design, professional lighting, 16:9 aspect ratio",
        ],
        "_output_path": None,
    }
