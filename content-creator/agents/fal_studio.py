"""FAL.ai image and video generation agent."""
import asyncio
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

FAL_KEY = os.environ.get("FAL_KEY", "") or os.environ.get("FAL_API_KEY", "")
FAL_BASE = "https://fal.run"

UNIVERSE_PRESETS = [
    {
        "id": "binary_star",
        "name": "Binary Star System",
        "prompt": "A breathtaking panoramic view of a distant binary star system with a massive ringed gas giant in deep teal and amber colors. Twin suns — one brilliant blue-white dwarf and one warm orange dwarf — cast contrasting light. A torus-shaped space station with crystalline architecture refracts the binary starlight into rainbow prisms. Nebula clouds in deep purples and magentas. Ultra-realistic concept art, cinematic lighting, 8K.",
    },
    {
        "id": "alien_mega",
        "name": "Alien Megastructure",
        "prompt": "An enormous space station shaped like a torus with crystalline spires extending from its surface. Orbits a binary star system. The station refracts light into rainbow prisms. Hexagonal energy collectors form a partial Dyson swarm around a distant star. Auroras dancing between celestial bodies with nebula clouds in deep purples and magentas. Cinematic sci-fi concept art, dramatic lighting.",
    },
    {
        "id": "nebula_core",
        "name": "Nebula Core",
        "prompt": "A cosmic nebula core with swirling gases in deep purples, teals, and golds. A massive ringed gas giant dominates the center with twin suns casting dramatic light and shadow. A torus-shaped space station with crystalline architecture refracts binary starlight into rainbow-colored light displays. Dyson swarm with hexagonal energy collectors in the background. Hyper-realistic space art.",
    },
    {
        "id": "jarvis_hud",
        "name": "JARVIS Interface",
        "prompt": "A futuristic holographic AI command center interface, Iron Man JARVIS style, multiple translucent blue HUD panels floating in dark space, neon cyan data streams, arc reactor glow, circuit board patterns, ultra high tech, cinematic, 8K detail.",
    },
    {
        "id": "content_empire",
        "name": "Content Empire",
        "prompt": "A vast digital empire visualized as floating platforms in cyberspace, each platform shows a different social media platform with streams of data and content flowing between them, YouTuber at the center commanding AI agents, vibrant neon colors, futuristic, ultra-detailed concept art.",
    },
]

IMAGE_MODELS = {
    "flux-schnell":  "fal-ai/flux/schnell",
    "flux-dev":      "fal-ai/flux/dev",
    "flux-pro":      "fal-ai/flux-pro",
    "sdxl":          "fal-ai/stable-diffusion-xl",
    "ideogram":      "fal-ai/ideogram/v2",
}

VIDEO_MODELS = {
    "kling-5s":  "fal-ai/kling-video/v1.6/standard/text-to-video",
    "hunyuan":   "fal-ai/hunyuan-video",
    "ltx":       "fal-ai/ltx-video",
    "cogvideo":  "fal-ai/cogvideox-5b",
    "minimax":   "fal-ai/minimax-video/text-to-video",
}


async def generate_image(
    prompt: str,
    model: str = "flux-schnell",
    width: int = 1024,
    height: int = 1024,
    num_images: int = 1,
    negative_prompt: str = "",
) -> dict:
    if not FAL_KEY:
        raise RuntimeError("FAL_KEY not set in environment")

    endpoint = IMAGE_MODELS.get(model, IMAGE_MODELS["flux-schnell"])
    payload: dict = {"prompt": prompt, "image_size": {"width": width, "height": height}, "num_images": num_images}
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    return await _fal_run(endpoint, payload)


async def generate_video(
    prompt: str,
    model: str = "kling-5s",
    duration: int = 5,
    aspect_ratio: str = "16:9",
) -> dict:
    if not FAL_KEY:
        raise RuntimeError("FAL_KEY not set in environment")

    endpoint = VIDEO_MODELS.get(model, VIDEO_MODELS["kling-5s"])
    payload = {"prompt": prompt, "duration": duration, "aspect_ratio": aspect_ratio}
    return await _fal_run(endpoint, payload)


async def _fal_run(endpoint: str, payload: dict) -> dict:
    url = f"{FAL_BASE}/{endpoint}"
    headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(url, json=payload, headers=headers)
        if r.status_code != 200:
            raise RuntimeError(f"FAL.ai error {r.status_code}: {r.text[:300]}")
        return r.json()
