"""Stage 3: Asset Generation Agent.

Takes script scenes from Stage 2 and generates visual assets via Pollinations.ai
with fallback to stock footage (Pexels/Pixabay via yt-dlp).

Output: outputs/assets/{topic_id}/scene_{n}.jpg
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Constants
ASSETS_BASE = Path(__file__).parent.parent / "outputs" / "assets"
POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"
DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1920  # Vertical for shorts/Reels


@dataclass
class AssetResult:
    """Result from asset generation."""
    ok: bool
    scene_e: list[str]
    assets: list[dict]  # {"path": str, "source": "pollinations"|"stock"|"fallback", "bytes": int}
    errors: list[str]
    elapsed_s: float


def _make_safe_filename(text: str, max_len: int = 60) -> str:
    """Convert scene text to a safe filename."""
    safe = re.sub(r"[^a-zA-Z0-9\s\-_]", "", text.lower())
    safe = re.sub(r"\s+", "-", safe).strip("-")
    return safe[:max_len] or "scene"


async def generate_assets(
    scenes: list[str],
    topic_id: str,
    n_images_per_scene: int = 5,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> AssetResult:
    """Generate visual assets for script scenes.

    Args:
        scenes: List of scene descriptions from Stage 2
        topic_id: Unique identifier for this topic (used in output path)
        n_images_per_scene: Number of image variations to generate per scene
        width: Image width (default 1080 for vertical)
        height: Image height (default 1920 for vertical)

    Returns:
        AssetResult with paths to generated assets
    """
    import time

    started = time.time()
    started = time.time()
    assets_dir = ASSETS_BASE / topic_id
    assets_dir.mkdir(parents=True, exist_ok=True)

    all_assets: list[dict] = []
    all_errors: list[str] = []
    all_scene_texts: list[str] = []

    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        tasks = [
            _generate_scene_assets(
                client, scene, topic_id, scene_idx, n_images_per_scene, width, height
            )
            for scene_idx, scene in enumerate(scenes)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for scene_idx, result in enumerate(results):
        scene_text = scenes[scene_idx] if scene_idx < len(scenes) else f"scene_{scene_idx}"

        if isinstance(result, dict) and result.get("ok"):
            all_assets.extend(result.get("assets", []))
            all_scene_texts.append(scene_text)
            if result.get("errors"):
                all_errors.extend(result["errors"])
        elif isinstance(result, dict):
            all_errors.append(f"Scene {scene_idx}: {result.get('error', 'unknown error')}")
            all_scene_texts.append(scene_text)
        else:
            all_errors.append(f"Scene {scene_idx}: {type(result).__name__}: {result}")
            all_scene_texts.append(scene_text)

    elapsed = time.time() - started

    if not all_assets:
        return AssetResult(
            ok=False,
            scene_texts=all_scene_texts,
            assets=[],
            errors=all_errors or ["No assets generated for any scenes"],
            elapsed_s=round(elapsed, 1),
        )

    return AssetResult(
        ok=True,
        scene_texts=all_scene_texts,
        assets=all_assets,
        errors=all_errors,
        elapsed_s=round(elapsed, 1),
    )


async def _generate_scene_assets(
    client: httpx.AsyncClient,
    scene: str,
    topic_id: str,
    scene_idx: int,
    n_images: int,
    width: int,
    height: int,
) -> dict:
    """Generate assets for a single scene with fallback chain.

    Fallback chain:
    1. Pollinations.ai (primary - free, high quality)
    2. Stock footage via yt-dlp (Pexels/Pixabay)
    3. Fallback placeholder generation
    """
    scene_id = _make_safe_filename(scene[:50])
    seed_base = scene_idx * 1000
    assets: list[dict] = []
    errors: list[str] = []

    # Try Pollinations.ai first
    pollinations_ok = await _try_pollinations(
        client, scene, topic_id, scene_idx, n_images, width, height, seed_base, assets, errors
    )

    if pollinations_ok:
        logger.info(f"Scene {scene_idx}: Generated {len(assets)} assets via Pollinations.ai")
        return {"ok": True, "assets": assets, "errors": errors}

    # Fallback to stock footage
    logger.warning(f"Scene {scene_idx}: Pollinations failed, trying stock footage")
    stock_result = await _try_stock_footage(client, scene, topic_id, scene_idx, width, height)

    if stock_result.get("ok"):
        assets.append(stock_result["asset"])
        logger.info(f"Scene {scene_idx}: Generated 1 asset via stock footage fallback")
        return {"ok": True, "assets": assets, "errors": errors + stock_result.get("errors", [])}

    # Final fallback: creates a simple placeholder
    logger.error(f"Scene {scene_idx}: All generation methods failed, using placeholder")
    placeholder = _create_placeholder(scene, topic_id, scene_idx, width, height)

    return {
        "ok": True,  # Partial success with fallback
        "assets": [placeholder],
        "errors": errors + ["Using placeholder (generation failed)"],
    }


async def _try_pollinations(
    client: httpx.AsyncClient,
    scene: str,
    topic_id: str,
    scene_idx: int,
    n_images: int,
    width: int,
    height: int,
    seed_base: int,
    assets: list[dict],
    errors: list[str],
) -> bool:
    """Try to generate images via Pollinations.ai.

    Returns True if successful, False otherwise.
    """
    encoded_scene = _encode_prompt(scene)

    for i in range(n_images):
        seed = seed_base + i
        url = (
            f"{POLLINATIONS_BASE}/{encoded_scene}"
            f"?model=flux&width={width}&height={height}"
            f"&seed={seed}&nologo=true&enhance=true"
        )

        try:
            response = await client.get(url, timeout=60)

            if response.status_code != 200:
                errors.append(f"Pollinations HTTP {response.status_code} for seed {seed}")
                continue

            content = response.content
            if not content or len(content) < 1024:
                errors.append(f"Pollinations returned invalid image ({len(content)} bytes) for seed {seed}")
                continue

            # Save the image
            safe_name = f"{topic_id}_scene{scene_idx}_var{i}_{seed}.jpg"
            asset_path = ASSETS_BASE / safe_name
            asset_path.write_bytes(content)

            assets.append({
                "path": str(asset_path),
                "source": "pollinations",
                "bytes": len(content),
                "seed": seed,
            })

        except httpx.TimeoutException:
            errors.append(f"Pollinations timeout for seed {seed}")
        except Exception as e:
            errors.append(f"Pollinations error seed {seed}: {type(e).__name__}: {e}")

    return len(assets) > 0


async def _try_stock_footage(
    client: httpx.AsyncClient,
    scene: str,
    topic_id: str,
    scene_idx: int,
    width: int,
    height: int,
) -> dict:
    """Try to download stock footage via yt-dlp.

    This is a fallback when AI generation fails.
    """
    import subprocess

    errors: list[str] = []

    # Try Pexels search via yt-dlp
    search_url = f"https://www.pexels.com/search/videos/{_encode_query(scene)}"

    try:
        # Use yt-dlp to find and download a video
        result = subprocess.run(
            [
                "yt-dlp",
                "--flat-playlist",
                "--print", "url",
                search_url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            errors.append(f"yt-dlp Pexels search failed: {result.stderr}")
            # Try Pixabay
            return await _try_pixabay(client, scene, topic_id, scene_idx, width, height)

        # Download the first result
        video_url = result.stdout.strip().split("\n")[0]
        output_path = ASSETS_BASE / f"{topic_id}_scene{scene_idx}_stock.mp4"

        result = subprocess.run(
            [
                "yt-dlp",
                "-f", "best[height<={}]".format(height),
                "-o", str(output_path),
                "--no-overwrites",
                video_url,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0 and output_path.exists():
            size = output_path.stat().st_size
            if size > 100_000:  # At least 100KB
                return {
                    "ok": True,
                    "asset": {
                        "path": str(output_path),
                        "source": "stock",
                        "bytes": size,
                        "type": "video",
                    },
                    "errors": errors,
                }

    except FileNotFoundError:
        errors.append("yt-dlp not found (install: uv pip install yt-dlp)")
    except subprocess.TimeoutExpired:
        errors.append("yt-dlp timeout")
    except Exception as e:
        errors.append(f"Stock footage error: {type(e).__name__}: {e}")

    # Try Pixabay as fallback
    return await _try_pixabay(client, scene, topic_id, scene_idx, width, height)


async def _try_pixabay(
    client: httpx.AsyncClient,
    scene: str,
    topic_id: str,
    scene_idx: int,
    width: int,
    height: int,
) -> dict:
    """Try Pixabay API for stock footage."""
    errors: list[str] = []

    # Pixabay API (free, no key required for basic usage)
    pixabay_url = (
        "https://pixabay.com/api/"
        f"?key=54294827-c74486f0c9736907513277234"  # Demo key
        f"&q={_encode_query(scene)}"
        "&image_type=video"
        "&per_page=3"
    )

    try:
        response = await client.get(pixabay_url, timeout=30)

        if response.status_code != 200:
            errors.append(f"Pixabay API HTTP {response.status_code}")
            return {"ok": False, "errors": errors}

        data = response.json()
        hits = data.get("hits", [])

        if not hits:
            errors.append("Pixabay returned no results")
            return {"ok": False, "errors": errors}

        # Download the first video
        video_info = hits[0]
        video_url = video_info.get("videos", {}).get("large", {}).get("url") or video_info.get("videos", {}).get("medium", {}).get("url")

        if not video_url:
            errors.append("Pixabay video has no download URL")
            return {"ok": False, "errors": errors}

        # Download the video
        video_response = await client.get(video_url, timeout=120)

        if video_response.status_code != 200:
            errors.append(f"Pixabay video download HTTP {video_response.status_code}")
            return {"ok": False, "errors": errors}

        content = video_response.content
        output_path = ASSETS_BASE / f"{topic_id}_scene{scene_idx}_pixabay.mp4"
        output_path.write_bytes(content)

        if len(content) > 100_000:
            return {
                "ok": True,
                "asset": {
                    "path": str(output_path),
                    "source": "stock",
                    "bytes": len(content),
                    "type": "video",
                },
                "errors": errors,
            }

    except Exception as e:
        errors.append(f"Pixabay error: {type(e).__name__}: {e}")

    return {"ok": False, "errors": errors}


def _create_placeholder(
    scene: str,
    topic_id: str,
    scene_idx: int,
    width: int,
    height: int,
) -> dict:
    """Create a simple text-based placeholder image.

    This uses PIL to create a basic colored background with text.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont

        # Create a gradient background
        img = Image.new("RGB", (width, height), color=(40, 40, 60))
        draw = ImageDraw.Draw(img)

        # Add text
        text = scene[:100]
        font_size = 48
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()

        # Center the text
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        x = (width - text_width) // 2
        y = (height - text_height) // 2

        draw.text((x, y), text, fill=(255, 255, 255), font=font)

        # Save
        output_path = ASSETS_BASE / f"{topic_id}_scene{scene_idx}_placeholder.jpg"
        img.save(output_path, "JPEG", quality=85)

        return {
            "path": str(output_path),
            "source": "placeholder",
            "bytes": output_path.stat().st_size,
        }

    except ImportError:
        # PIL not available, create minimal valid JPEG
        import struct
        import zlib

        # Minimal 1x1 JPEG (actually creates a tiny valid JPEG)
        # This is a degenerate case - just save and note the issue
        output_path = ASSETS_BASE / f"{topic_id}_scene{scene_idx}_min.jpeg"

        # Create a simple grayscale image
        pixel = bytes([128])
        raw = zlib.compress(pixel, 9)

        # Minimal JPEG-like placeholder (actually PGM converted)
        with open(output_path, "wb") as f:
            f.write(b"P5\n1 1\n255\n" + pixel)

        return {
            "path": str(output_path),
            "source": "placeholder",
            "bytes": output_path.stat().st_size,
        }


def _encode_prompt(text: str) -> str:
    """Encode prompt for URL."""
    return text.replace(" ", "%20").replace("\n", "%0A")


def _encode_query(text: str) -> str:
    """Encode search query."""
    import urllib.parse

    return urllib.parse.quote(text)