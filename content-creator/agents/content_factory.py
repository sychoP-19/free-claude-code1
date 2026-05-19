import re
import json
from datetime import datetime
from pathlib import Path
from core import ollama_client as ollama

# Output directories
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
    "viral":     "extremely catchy, controversial, pattern-interrupting",
    "edu":       "educational but entertaining, simplify complex topics",
    "story":     "personal story, emotional, relatable struggles",
    "listicle":  "numbered list, each point builds on the last",
}


async def run(topic: str, style: str, tone: str, gen_script: bool = True,
              gen_thumbnail: bool = True, gen_hashtags: bool = True,
              topic_id: str = None, output_file: bool = True) -> dict:
    """
    Generate a complete content package from a selected topic (Stage 2).

    Args:
        topic: Selected topic/title from Stage 1
        style: Content style (shorts, tiktok, reel, longform)
        tone: Content tone (viral, edu, story, listicle)
        gen_script: Whether to generate script
        gen_thumbnail: Whether to generate thumbnail prompts
        gen_hashtags: Whether to generate platform-specific hashtags
        topic_id: Topic identifier from Stage 1
        output_file: If True, write to outputs/scripts/{topic_id}.json

    Returns:
        Dict with script, scenes, hashtags, thumbnail prompts
    """
    models = await ollama.list_models()
    model = ollama.pick_model(models, ["mistral:7b", "llama3:8b", "phi3:mini"])

    style_desc = STYLE_NOTES.get(style, style)
    tone_desc  = TONE_NOTES.get(tone, tone)

    prompt = f"""Create a complete 60-second short-form video content package for: "{topic}"
Format: {style_desc}
Tone: {tone_desc}

Return JSON with this exact structure:
{{
  "topic_id": "{topic_id or 'manual'}",
  "topic": "{topic}",
  "style": "{style}",
  "tone": "{tone}",
  "duration_seconds": 60,
  "script": {{
    "hook": "0-3s attention grabber text",
    "body": "3-45s main content with 3 key points",
    "cta": "45-60s call to action text"
  }},
  "scenes": [
    {{"scene_number": 1, "description": "visual description", "timing": "0-8s", "text_overlay": "on-screen text"}},
    {{"scene_number": 2, "description": "visual description", "timing": "8-18s", "text_overlay": "on-screen text"}},
    {{"scene_number": 3, "description": "visual description", "timing": "18-28s", "text_overlay": "on-screen text"}},
    {{"scene_number": 4, "description": "visual description", "timing": "28-38s", "text_overlay": "on-screen text"}},
    {{"scene_number": 5, "description": "visual description", "timing": "38-48s", "text_overlay": "on-screen text"}},
    {{"scene_number": 6, "description": "visual description", "timing": "48-60s", "text_overlay": "on-screen text"}}
  ],
  "hashtags": {{
    "youtube": ["#tag1","#tag2","#tag3","#tag4","#tag5","#tag6","#tag7","#tag8","#tag9","#tag10"],
    "tiktok": ["#tag1","#tag2","#tag3","#tag4","#tag5","#tag6","#tag7","#tag8","#tag9","#tag10"],
    "instagram": ["#tag1","#tag2","#tag3","#tag4","#tag5","#tag6","#tag7","#tag8","#tag9","#tag10"]
  }},
  "thumbnail_prompts": [
    "prompt for AI image generation - concept 1",
    "prompt for AI image generation - concept 2",
    "prompt for AI image generation - concept 3"
  ]
}}

Return only JSON, no additional text."""

    try:
        response = await ollama.generate(model, prompt, system=SYSTEM_PROMPT)
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            result = json.loads(match.group())

            # Write to file if requested
            if output_file:
                file_id = topic_id or f"script_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                output_path = SCRIPTS_DIR / f"{file_id}.json"
                result["_output_path"] = str(output_path)
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)

            return result
    except Exception as e:
        print(f"Content factory Ollama error: {e}")
        pass

    result = _fallback(topic, style, tone, topic_id)

    # Write fallback to file if requested
    if output_file:
        file_id = topic_id or f"script_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        output_path = SCRIPTS_DIR / f"{file_id}.json"
        result["_output_path"] = str(output_path)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    return result


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
