"""pipelines/carousel.py — 10-slide social carousel with Pillow text overlay.

Includes:
  CarouselPipeline – original Pollinations-backed carousel
  generate_story_carousel() – fully offline, Pillow-rendered story arc (no external API)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

from pipelines.base import PipelineRun, OUTPUTS, build_system_prompt, slugify
from pipelines.llm import chat


class CarouselPipeline(PipelineRun):
    pipeline = "carousel"
    publish_platforms = ("instagram", "linkedin")

    async def execute(self) -> tuple[str, dict]:
        topic = self.params.get("topic", "").strip()
        slides = int(self.params.get("slides", 10))
        if not topic:
            raise ValueError("topic is required")

        slug = slugify(topic)
        out_dir = OUTPUTS / "carousel" / slug
        out_dir.mkdir(parents=True, exist_ok=True)

        await self.set_stage("script", 20)
        await self.emit("writer", "act", f"Writing {slides}-slide narrative")
        deck = await self._deck(topic, slides)
        if len(deck) < 3:
            raise RuntimeError("narrative produced too few slides")

        await self.set_stage("visuals", 50)
        await self.emit("designer", "act", "Generating backgrounds + overlays")
        paths: list[str] = []
        async with httpx.AsyncClient(timeout=120) as client:
            for i, slide in enumerate(deck):
                bg_path = out_dir / f"_bg_{i+1:02d}.jpg"
                ok = await self._pollinations(client, slide.get("visual") or slide["text"], bg_path, w=1080, h=1080)
                final = out_dir / f"slide_{i+1:02d}.png"
                if ok:
                    self._overlay_text(bg_path, slide["text"], i + 1, len(deck), final)
                    if final.exists() and final.stat().st_size > 50_000:
                        paths.append(str(final))

        if not paths:
            raise RuntimeError("no slides produced")

        # Caption file
        caption = out_dir / "caption.txt"
        caption.write_text("\n\n".join(s["text"] for s in deck), encoding="utf-8")

        # Index json so we know the slide order
        idx = out_dir / "index.json"
        idx.write_text(json.dumps({"topic": topic, "slug": slug, "slides": deck}, indent=2),
                       encoding="utf-8")

        for p in paths:
            self.track_asset("image", p, caption=topic, tags=["carousel", slug])
        self.track_asset("text", str(caption), caption="carousel caption", tags=["caption", slug])

        await self.set_stage("assembly", 100)
        return paths[0], {"slug": slug, "slides_made": len(paths), "out_dir": str(out_dir)}

    async def _deck(self, topic: str, slides: int) -> list[dict]:
        prompt = (
            f"Write a {slides}-slide social carousel on: {topic}.\n"
            f"Slide 1 is a hook (max 7 words). Slides 2-{slides-1} are value (max 20 words each). "
            f"Slide {slides} is a CTA.\n"
            f"Return JSON array with objects: {{\"text\": \"...\", \"visual\": \"image prompt\"}}."
        )
        try:
            reply = await chat(
                [{"role": "user", "content": prompt}],
                system=build_system_prompt("writer"),
                max_tokens=1200, run_id=self.run_id,
            )
            m = re.search(r"\[.*\]", reply, re.DOTALL)
            if m:
                arr = json.loads(m.group())
                return [{"text": str(s.get("text", "")), "visual": str(s.get("visual", ""))}
                        for s in arr if s.get("text")]
        except Exception:
            pass
        return [{"text": f"Slide {i+1} about {topic}", "visual": topic} for i in range(slides)]

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

    def _overlay_text(self, bg_path: Path, text: str, idx: int, total: int, dest: Path) -> None:
        from PIL import Image, ImageDraw, ImageFont, ImageFilter
        img = Image.open(bg_path).convert("RGB").filter(ImageFilter.GaussianBlur(radius=2))
        w, h = img.size

        # Dark gradient overlay for legibility
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        for y in range(h):
            alpha = int(180 * (y / h) ** 1.5)
            d.line([(0, y), (w, y)], fill=(0, 8, 20, alpha))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

        d = ImageDraw.Draw(img)
        # Try a clean system font; fall back to default if unavailable
        font_main, font_meta = None, None
        for f in ("arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"):
            try:
                font_main = ImageFont.truetype(f, 64)
                font_meta = ImageFont.truetype(f, 28)
                break
            except Exception:
                continue
        if not font_main:
            font_main = ImageFont.load_default()
            font_meta = ImageFont.load_default()

        # Word-wrap to ~22 chars per line
        words = text.split()
        lines: list[str] = []
        cur = ""
        for w_ in words:
            test = (cur + " " + w_).strip()
            if len(test) > 22 and cur:
                lines.append(cur)
                cur = w_
            else:
                cur = test
        if cur:
            lines.append(cur)

        # Draw centered, lower-third
        total_h = len(lines) * 78
        y = h - 220 - total_h
        for line in lines:
            tw = d.textlength(line, font=font_main)
            d.text(((w - tw) / 2, y), line, fill=(255, 255, 255), font=font_main)
            y += 78

        # Pagination meta
        meta = f"{idx} / {total}"
        d.text((w - 120, h - 60), meta, fill=(0, 212, 255), font=font_meta)

        img.save(dest, "PNG", optimize=True)


async def run(params: dict) -> dict:
    res = await CarouselPipeline(params).run()
    return res.__dict__


# ─────────────────────────────────────────────────────────────────────────────
# Story Mode carousel — fully offline, Pillow-rendered narrative arc
# ─────────────────────────────────────────────────────────────────────────────

# JARVIS brand palette (plasma/cyan from CSS tokens)
_GRADIENT_PAIRS: list[tuple[tuple[int, int, int], tuple[int, int, int]]] = [
    ((10, 10, 15), (0, 30, 60)),     # deep space → midnight blue
    ((10, 10, 15), (20, 0, 50)),     # deep space → dark violet
    ((10, 10, 15), (0, 40, 50)),     # deep space → dark teal
    ((5, 0, 25), (30, 0, 70)),       # void → deep purple
    ((0, 15, 30), (0, 50, 80)),      # abyss → ocean deep
]
_CYAN   = (0, 212, 255)   # #00d4ff — JARVIS accent
_WHITE  = (255, 255, 255)
_DIM    = (140, 160, 180)  # muted secondary text


# Narrative arc labels — visible label + colour pulse
_STORY_ACTS = [
    ("SETUP",      (0, 212, 255)),
    ("SETUP",      (0, 212, 255)),
    ("RISING",     (80, 200, 255)),
    ("RISING",     (80, 200, 255)),
    ("CONFLICT",   (255, 130, 60)),
    ("CONFLICT",   (255, 130, 60)),
    ("CLIMAX",     (255, 60, 100)),
    ("FALLING",    (120, 255, 180)),
    ("RESOLUTION", (0, 255, 180)),
    ("CTA",        (0, 212, 255)),
]


async def _story_deck(topic: str, style: str) -> list[dict]:
    """Ask LLM for a 10-slide narrative arc; fall back to template."""
    style_hint = {
        "educational": "educational and insightful, each slide teaches something concrete",
        "motivational": "motivational story arc with tension and triumph",
        "brand": "brand story arc that builds credibility and ends with a CTA",
    }.get(style, "educational and insightful")

    prompt = (
        f"Write a 10-slide narrative carousel story on: {topic}.\n"
        f"Style: {style_hint}.\n"
        f"The arc MUST follow: setup (slides 1-2) → rising action (3-4) → conflict (5-6) → "
        f"climax (7) → falling action (8) → resolution (9) → CTA (10).\n"
        f"Rules: slide 1 is a hook (≤8 words). Slides 2-9 are 1-2 punchy sentences (≤25 words each). "
        f"Slide 10 is a strong action CTA (≤12 words).\n"
        f"Return a JSON array of 10 objects: {{\"text\": \"...\", \"subtext\": \"brief context or stat\"}}."
    )
    try:
        reply = await chat(
            [{"role": "user", "content": prompt}],
            system=build_system_prompt("writer"),
            max_tokens=1400,
        )
        m = re.search(r"\[.*\]", reply, re.DOTALL)
        if m:
            arr = json.loads(m.group())
            if len(arr) >= 8:
                return [{"text": str(s.get("text", "")), "subtext": str(s.get("subtext", ""))}
                        for s in arr]
    except Exception:
        pass

    # Minimal fallback
    acts = ["Hook", "Context", "Rising", "Challenge", "Conflict",
            "Struggle", "Climax", "Turning Point", "Resolution", "Take Action"]
    return [{"text": f"{acts[i]}: {topic}", "subtext": ""} for i in range(10)]


def _render_story_slide(
    text: str,
    subtext: str,
    slide_num: int,       # 1-based
    total: int,
    act_label: str,
    act_color: tuple[int, int, int],
    dest: Path,
    w: int = 1080,
    h: int = 1080,
) -> None:
    """Render a single story slide entirely with Pillow — no external API."""
    from PIL import Image, ImageDraw, ImageFont

    # 1. Dark gradient background
    grad_top, grad_bot = _GRADIENT_PAIRS[slide_num % len(_GRADIENT_PAIRS)]
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        r = int(grad_top[0] + (grad_bot[0] - grad_top[0]) * t)
        g = int(grad_top[1] + (grad_bot[1] - grad_top[1]) * t)
        b = int(grad_top[2] + (grad_bot[2] - grad_top[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # 2. Decorative cyan accent bar (top)
    bar_h = 6
    for x in range(w):
        t = x / w
        r = int(act_color[0] * (1 - t) + _CYAN[0] * t)
        g = int(act_color[1] * (1 - t) + _CYAN[1] * t)
        b = int(act_color[2] * (1 - t) + _CYAN[2] * t)
        draw.line([(x, 0), (x, bar_h)], fill=(r, g, b))

    # 3. Subtle grid lines for depth
    grid_alpha = 18
    for x in range(0, w, 90):
        draw.line([(x, 0), (x, h)], fill=(0, 212, 255, grid_alpha))
    for y in range(0, h, 90):
        draw.line([(0, y), (w, y)], fill=(0, 212, 255, grid_alpha))

    # 4. Load fonts (graceful fallback)
    font_hook, font_body, font_sub, font_meta = (None,) * 4
    for f in ("arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"):
        try:
            font_hook = ImageFont.truetype(f, 72)
            font_body = ImageFont.truetype(f, 56)
            font_sub  = ImageFont.truetype(f, 30)
            font_meta = ImageFont.truetype(f, 26)
            break
        except Exception:
            continue
    if not font_hook:
        font_hook = font_body = font_sub = font_meta = ImageFont.load_default()

    is_hook = slide_num == 1

    # 5. Word-wrap main text
    font_used = font_hook if is_hook else font_body
    max_chars = 18 if is_hook else 24
    words = text.split()
    lines: list[str] = []
    cur = ""
    for word in words:
        test = (cur + " " + word).strip()
        if len(test) > max_chars and cur:
            lines.append(cur)
            cur = word
        else:
            cur = test
    if cur:
        lines.append(cur)

    line_h = 90 if is_hook else 70
    total_text_h = len(lines) * line_h
    if subtext:
        total_text_h += 50   # extra room for subtext

    # 6. Center-align text block vertically
    start_y = (h - total_text_h) // 2 - 20

    for i, line in enumerate(lines):
        tw = draw.textlength(line, font=font_used)
        x = (w - tw) / 2
        y = start_y + i * line_h
        # Subtle shadow
        draw.text((x + 2, y + 2), line, fill=(0, 0, 0, 180), font=font_used)
        draw.text((x, y), line, fill=_WHITE if not is_hook else _CYAN, font=font_used)

    # 7. Subtext below main text
    if subtext:
        tw = draw.textlength(subtext, font=font_sub)
        x = (w - tw) / 2
        y = start_y + len(lines) * line_h + 12
        draw.text((x, y), subtext, fill=_DIM, font=font_sub)

    # 8. Act label badge (bottom-left)
    badge_x, badge_y = 36, h - 80
    badge_text = act_label
    badge_w = draw.textlength(badge_text, font=font_meta) + 24
    draw.rounded_rectangle(
        [badge_x, badge_y, badge_x + badge_w, badge_y + 40],
        radius=8,
        fill=(*act_color, 60),    # semi-transparent
        outline=act_color,
    )
    draw.text((badge_x + 12, badge_y + 6), badge_text, fill=act_color, font=font_meta)

    # 9. Slide counter (bottom-right) — e.g. "3/10"
    counter = f"{slide_num}/{total}"
    cw = draw.textlength(counter, font=font_meta)
    draw.text((w - cw - 36, h - 74), counter, fill=_CYAN, font=font_meta)

    # 10. JARVIS brand mark (top-right corner, tiny)
    brand = "JARVIS"
    bw = draw.textlength(brand, font=font_meta)
    draw.text((w - bw - 24, 20), brand, fill=(*_CYAN, 140), font=font_meta)

    img.save(dest, "PNG", optimize=True)


async def generate_story_carousel(
    topic: str,
    style: str = "educational",
    run_id: int | None = None,
) -> dict:
    """
    Generate a 10-slide story carousel rendered entirely with Pillow.

    Returns:
        {
          "ok": True,
          "slug": str,
          "out_dir": str,
          "slides": ["/abs/path/slide_01.png", ...],
          "index": "/abs/path/index.json",
        }
    """
    slug = slugify(topic)
    out_dir = OUTPUTS / "carousel" / slug / "story"
    out_dir.mkdir(parents=True, exist_ok=True)

    deck = await _story_deck(topic, style)
    if len(deck) < 8:
        raise RuntimeError(f"story deck too short: got {len(deck)} slides")

    slides_info: list[dict] = []
    paths: list[str] = []

    for i, slide in enumerate(deck):
        act_label, act_color = _STORY_ACTS[i] if i < len(_STORY_ACTS) else ("", _CYAN)
        dest = out_dir / f"slide_{i+1:02d}.png"
        _render_story_slide(
            text=slide["text"],
            subtext=slide.get("subtext", ""),
            slide_num=i + 1,
            total=len(deck),
            act_label=act_label,
            act_color=act_color,
            dest=dest,
        )
        if dest.exists() and dest.stat().st_size > 0:
            paths.append(str(dest))
            slides_info.append({
                "slide": i + 1,
                "act": act_label,
                "text": slide["text"],
                "subtext": slide.get("subtext", ""),
                "path": str(dest),
            })

    if not paths:
        raise RuntimeError("no story slides rendered")

    index = out_dir / "index.json"
    index.write_text(
        json.dumps({"topic": topic, "style": style, "slug": slug, "slides": slides_info}, indent=2),
        encoding="utf-8",
    )

    # ── Video slideshow: 3s per slide, no audio ──────────────────────────────
    video_path: str | None = None
    try:
        video_path = _make_slideshow_video(paths, out_dir / "slideshow.mp4", seconds_per_slide=3)
    except Exception:
        pass  # video is a bonus; don't fail if ffmpeg is unavailable

    return {
        "ok": True,
        "slug": slug,
        "out_dir": str(out_dir),
        "slides": paths,
        "index": str(index),
        "video": video_path,
    }


def _make_slideshow_video(slide_paths: list[str], dest: Path, seconds_per_slide: int = 3) -> str | None:
    """Concatenate slide PNGs into a video at <seconds_per_slide> per image.

    Returns the absolute path to the output mp4, or None on failure.
    """
    import subprocess
    from pathlib import Path as _Path

    if not slide_paths:
        return None

    # Write a concat list that ffmpeg understands
    list_file = dest.parent / "_slide_list.txt"
    lines: list[str] = []
    for p in slide_paths:
        lines.append(f"file '{p}'")
        lines.append(f"duration {seconds_per_slide}")
    # ffmpeg concat demuxer needs the last file repeated without a duration
    lines.append(f"file '{slide_paths[-1]}'")
    list_file.write_text("\n".join(lines), encoding="utf-8")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-vf", "scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2:black",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", "24",
        str(dest),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode == 0 and dest.exists() and dest.stat().st_size > 1000:
            return str(dest)
    except Exception:
        pass
    return None
