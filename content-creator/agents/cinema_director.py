import re
import json
import time
from pathlib import Path
from core import ollama_client as ollama
from core.downloader import download_video, DOWNLOADS_DIR
from core.video_processor import images_to_video, clip_video, concat_videos, OUTPUTS_DIR


SYSTEM_PROMPT = "You are a cinematic AI director. Return ONLY valid JSON."


async def run(data: dict) -> dict:
    mode = data.get("mode", "prompt")
    if mode == "images":
        return await _compile_images(data)
    if mode == "remix":
        return await _remix(data)
    return await _prompt_to_short(data)


async def _prompt_to_short(data: dict) -> dict:
    models = await ollama.list_models()
    model = ollama.pick_model(models, ["mistral:7b", "llama3:8b", "phi3:mini"])

    prompt_text = data.get("prompt", "cinematic scene")
    style       = data.get("style", "cinematic")
    duration    = data.get("duration", 30)
    music       = data.get("music", "none")

    script_prompt = f"""Write a {duration}-second {style} video script for: "{prompt_text}"

Return JSON:
{{
  "script": "full script with timestamps",
  "shots": [
    {{"scene": "scene description", "duration": 5, "camera": "close-up"}},
    {{"scene": "scene description", "duration": 10, "camera": "wide shot"}},
    {{"scene": "scene description", "duration": 15, "camera": "medium shot"}}
  ],
  "color_grade": "describe color treatment",
  "music_suggestion": "describe ideal music",
  "output_filename": "output_{int(time.time())}.mp4"
}}

Return only JSON."""

    script_data = {}
    try:
        resp = await ollama.generate(model, script_prompt, system=SYSTEM_PROMPT)
        match = re.search(r'\{.*\}', resp, re.DOTALL)
        if match:
            script_data = json.loads(match.group())
    except Exception:
        pass

    # Honesty: this mode produces a SCRIPT only — no video yet.
    # Real video rendering lives in pipelines/longform.py and pipelines/shorts.py.
    # Returning ok=False with stage="script_only" tells the UI to surface this.
    return {
        "ok":          False,
        "stage":       "script_only",
        "output_path": "",
        "script":      script_data.get("script", _fallback_script(prompt_text, duration)),
        "shots":       script_data.get("shots", []),
        "style":       style,
        "duration":    duration,
        "next":        "Use /api/pipelines/longform/run or /api/pipelines/shorts/run for real MP4 export.",
    }


async def _compile_images(data: dict) -> dict:
    folder = Path(data.get("folder", "outputs/images"))
    fps    = int(data.get("fps", 30))
    trans  = data.get("transition", "fade")
    result = await images_to_video(folder, fps=fps, transition=trans)
    return result


async def _remix(data: dict) -> dict:
    url   = data.get("url", "")
    style = data.get("style", "highlights")

    dl = await download_video(url, DOWNLOADS_DIR)
    source = Path(dl["path"])

    if style == "first60":
        result = await clip_video(source, start=0, end=60)
    elif style == "viral-cut":
        result = await clip_video(source, start=30, end=90)
    else:
        result = await clip_video(source, start=0, end=60)

    return {**result, "script": f"Remix of {url} — style: {style}"}


def _fallback_script(prompt: str, duration: int) -> str:
    return f"""[0-3s] ESTABLISHING SHOT
Wide angle establishing the scene: {prompt}

[3-{duration//2}s] MAIN ACTION
Camera slowly pushes in. Subject fills frame.
Color grade: cinematic teal-orange.

[{duration//2}-{duration}s] RESOLUTION
Pull back to wide. Text overlay fades in.
Music swells to climax.

CUT TO BLACK."""
