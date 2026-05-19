"""pipelines/story_video.py — 5-panel story video pipeline.

Arc: setup → rising → climax → falling → resolution

Each panel:
  1. Pillow renders a 1080×1920 portrait image (dark gradient + text)
  2. gTTS narrates the panel text to mp3
  3. ffmpeg assembles panels + audio with 1s crossfade transitions

Output: outputs/story/<slug>/video.mp4
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

from pipelines.base import PipelineRun, OUTPUTS, build_system_prompt, slugify
from pipelines.llm import chat

# ── Design constants (JARVIS dark plasma palette) ─────────────────────────────
_W, _H       = 1080, 1920          # portrait 9:16
_BG          = (10, 10, 15)        # #0a0a0f
_CYAN        = (0, 212, 255)       # #00d4ff
_WHITE       = (255, 255, 255)
_DIM         = (130, 155, 180)

# One gradient pair per act: (top_rgb, bottom_rgb)
_ACT_GRADIENTS: dict[str, tuple[tuple[int,int,int], tuple[int,int,int]]] = {
    "SETUP":      ((10, 10, 15), (0, 25, 55)),
    "RISING":     ((10, 10, 20), (0, 20, 60)),
    "CLIMAX":     ((20, 5, 10),  (60, 0, 30)),
    "FALLING":    ((5, 15, 20),  (0, 40, 50)),
    "RESOLUTION": ((5, 20, 15),  (0, 50, 40)),
}
_ACT_ACCENT: dict[str, tuple[int,int,int]] = {
    "SETUP":      (0, 212, 255),
    "RISING":     (80, 200, 255),
    "CLIMAX":     (255, 60, 100),
    "FALLING":    (120, 255, 180),
    "RESOLUTION": (0, 255, 180),
}
_ACTS = ["SETUP", "RISING", "CLIMAX", "FALLING", "RESOLUTION"]


# ── LLM script generation ─────────────────────────────────────────────────────

async def _generate_script(topic: str, style: str) -> list[dict]:
    """Return 5 panels: [{act, title, narration, visual_detail}]."""
    style_hint = {
        "educational": "educational explainer — teach, don't preach",
        "motivational": "emotional motivation arc with tension and payoff",
        "brand": "brand story that builds trust and ends with a clear CTA",
    }.get(style, "educational explainer")

    prompt = (
        f"Write a 5-panel short-video story script on: {topic}.\n"
        f"Style: {style_hint}.\n"
        f"Panels: SETUP, RISING, CLIMAX, FALLING, RESOLUTION.\n"
        f"Each panel needs:\n"
        f"  - 'act': one of the 5 act names above (exact string)\n"
        f"  - 'title': 4-7 word panel headline\n"
        f"  - 'narration': 2-3 sentences spoken aloud (20-40 words). Punchy. No filler.\n"
        f"  - 'visual_detail': 1 sentence describing the background mood\n"
        f"Return a JSON array of exactly 5 objects."
    )
    try:
        reply = await chat(
            [{"role": "user", "content": prompt}],
            system=build_system_prompt("writer"),
            max_tokens=1000,
        )
        m = re.search(r"\[.*\]", reply, re.DOTALL)
        if m:
            arr = json.loads(m.group())
            panels = []
            for i, p in enumerate(arr[:5]):
                act = str(p.get("act", _ACTS[i])).upper()
                if act not in _ACTS:
                    act = _ACTS[i]
                panels.append({
                    "act":           act,
                    "title":         str(p.get("title", f"{act}: {topic}")),
                    "narration":     str(p.get("narration", f"This is the {act.lower()} of the story.")),
                    "visual_detail": str(p.get("visual_detail", "")),
                })
            if len(panels) == 5:
                return panels
    except Exception:
        pass

    # Fallback
    return [
        {
            "act":       act,
            "title":     f"{act.capitalize()}: {topic}",
            "narration": f"This is the {act.lower()} of our story about {topic}.",
            "visual_detail": "",
        }
        for act in _ACTS
    ]


# ── Pillow panel renderer ─────────────────────────────────────────────────────

def _render_panel(panel: dict, panel_num: int, total: int, dest: Path) -> None:
    """Render a single 1080×1920 story panel as PNG."""
    from PIL import Image, ImageDraw, ImageFont

    act   = panel["act"]
    title = panel["title"]
    narr  = panel["narration"]

    grad_top, grad_bot = _ACT_GRADIENTS.get(act, (_BG, _BG))
    accent             = _ACT_ACCENT.get(act, _CYAN)

    # Background gradient
    img  = Image.new("RGB", (_W, _H))
    draw = ImageDraw.Draw(img)
    for y in range(_H):
        t = y / _H
        r = int(grad_top[0] + (grad_bot[0] - grad_top[0]) * t)
        g = int(grad_top[1] + (grad_bot[1] - grad_top[1]) * t)
        b = int(grad_top[2] + (grad_bot[2] - grad_top[2]) * t)
        draw.line([(0, y), (_W, y)], fill=(r, g, b))

    # Subtle dot grid overlay
    for gx in range(0, _W, 80):
        for gy in range(0, _H, 80):
            draw.ellipse([(gx-1, gy-1), (gx+1, gy+1)], fill=(*accent, 25))

    # Top accent stripe
    for x in range(_W):
        t = x / _W
        cr = int(accent[0] * (1 - t) + _CYAN[0] * t)
        cg = int(accent[1] * (1 - t) + _CYAN[1] * t)
        cb = int(accent[2] * (1 - t) + _CYAN[2] * t)
        draw.line([(x, 0), (x, 8)], fill=(cr, cg, cb))

    # Fonts (graceful fallback chain)
    f_title = f_narr = f_act = f_pg = None
    for fname in ("arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"):
        try:
            f_title = ImageFont.truetype(fname, 80)
            f_narr  = ImageFont.truetype(fname, 48)
            f_act   = ImageFont.truetype(fname, 34)
            f_pg    = ImageFont.truetype(fname, 28)
            break
        except Exception:
            continue
    if not f_title:
        f_title = f_narr = f_act = f_pg = ImageFont.load_default()

    # Act badge (upper-center)
    act_text = act
    act_w    = draw.textlength(act_text, font=f_act) + 32
    ax       = (_W - act_w) / 2
    ay       = 60
    draw.rounded_rectangle([ax, ay, ax + act_w, ay + 48], radius=10,
                            fill=(*accent, 40), outline=accent)
    draw.text((ax + 16, ay + 7), act_text, fill=accent, font=f_act)

    # Title — word-wrap at ~20 chars
    t_lines: list[str] = []
    cur = ""
    for w_ in title.split():
        test = (cur + " " + w_).strip()
        if len(test) > 20 and cur:
            t_lines.append(cur)
            cur = w_
        else:
            cur = test
    if cur:
        t_lines.append(cur)

    title_top = _H // 3
    for i, ln in enumerate(t_lines):
        lw = draw.textlength(ln, font=f_title)
        draw.text((_W/2 - lw/2 + 2, title_top + i*96 + 2), ln,
                  fill=(0, 0, 0, 160), font=f_title)
        draw.text((_W/2 - lw/2,     title_top + i*96),     ln,
                  fill=_WHITE, font=f_title)

    # Narration — word-wrap at ~28 chars
    narr_top = title_top + len(t_lines) * 96 + 60
    n_lines: list[str] = []
    cur = ""
    for w_ in narr.split():
        test = (cur + " " + w_).strip()
        if len(test) > 28 and cur:
            n_lines.append(cur)
            cur = w_
        else:
            cur = test
    if cur:
        n_lines.append(cur)

    for i, ln in enumerate(n_lines):
        lw = draw.textlength(ln, font=f_narr)
        draw.text((_W/2 - lw/2, narr_top + i*64), ln, fill=_DIM, font=f_narr)

    # Cyan divider line between title and narration
    div_y = narr_top - 24
    draw.line([(120, div_y), (_W - 120, div_y)], fill=accent, width=2)

    # Page indicator bottom-right
    pg = f"{panel_num}/{total}"
    pw = draw.textlength(pg, font=f_pg)
    draw.text((_W - pw - 40, _H - 80), pg, fill=_CYAN, font=f_pg)

    # JARVIS brand bottom-left
    draw.text((40, _H - 80), "JARVIS", fill=(*_CYAN, 120), font=f_pg)

    img.save(dest, "PNG", optimize=True)


# ── gTTS narration ────────────────────────────────────────────────────────────

def _tts_panel(text: str, dest: Path) -> bool:
    """Synthesize narration to mp3 via gTTS. Returns True on success."""
    try:
        from gtts import gTTS  # type: ignore[import]
        tts = gTTS(text=text, lang="en", slow=False)
        tts.save(str(dest))
        return dest.exists() and dest.stat().st_size > 0
    except Exception:
        return False


# ── ffmpeg assembly ───────────────────────────────────────────────────────────

def _ffmpeg(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["ffmpeg", "-y", *args],
                          capture_output=True, text=True, check=check)


def _assemble_video(
    panels: list[dict],
    img_paths: list[Path],
    audio_paths: list[Path | None],
    out_path: Path,
    crossfade_s: float = 1.0,
) -> None:
    """
    Assemble panel images + per-panel audio into a single MP4.
    Steps:
      1. Per panel: image → silent video at panel-audio duration (or 5s fallback)
      2. Add audio track to each panel clip
      3. Concatenate with xfade transitions (1s crossfade)
    """
    tmp = Path(tempfile.mkdtemp(prefix="jarvis_sv_"))
    panel_clips: list[Path] = []

    for i, (panel, img_p, aud_p) in enumerate(zip(panels, img_paths, audio_paths)):
        # Determine duration from audio or default to 5s
        dur = 5.0
        if aud_p and aud_p.exists() and aud_p.stat().st_size > 0:
            try:
                probe = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", str(aud_p)],
                    capture_output=True, text=True, check=True,
                )
                dur = float(probe.stdout.strip()) + 0.5   # 0.5s breathing room
            except Exception:
                dur = 5.0

        panel_out = tmp / f"panel_{i:02d}.mp4"

        if aud_p and aud_p.exists() and aud_p.stat().st_size > 0:
            _ffmpeg(
                "-loop", "1", "-i", str(img_p),
                "-i", str(aud_p),
                "-c:v", "libx264", "-tune", "stillimage",
                "-c:a", "aac", "-b:a", "128k",
                "-pix_fmt", "yuv420p",
                "-shortest", "-t", str(dur),
                "-vf", f"scale={_W}:{_H}",
                str(panel_out),
            )
        else:
            _ffmpeg(
                "-loop", "1", "-i", str(img_p),
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-c:v", "libx264", "-tune", "stillimage",
                "-c:a", "aac", "-b:a", "128k",
                "-pix_fmt", "yuv420p",
                "-t", str(dur),
                "-vf", f"scale={_W}:{_H}",
                str(panel_out),
            )

        if panel_out.exists() and panel_out.stat().st_size > 0:
            panel_clips.append(panel_out)

    if not panel_clips:
        raise RuntimeError("ffmpeg produced no panel clips")

    if len(panel_clips) == 1:
        import shutil
        shutil.copy2(panel_clips[0], out_path)
        return

    # Concatenate with xfade transitions
    # Build complex filter: [0][1]xfade=transition=fade:duration=1:offset=<d0-1>[v01];...
    filter_parts: list[str] = []
    input_args: list[str] = []
    for clip in panel_clips:
        input_args += ["-i", str(clip)]

    # Compute offsets (cumulative duration - crossfade_s for each pair)
    durations: list[float] = []
    for clip in panel_clips:
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(clip)],
                capture_output=True, text=True, check=True,
            )
            durations.append(float(probe.stdout.strip()))
        except Exception:
            durations.append(5.0)

    # Build xfade chain
    prev = "[0:v]"
    aprev = "[0:a]"
    offset = 0.0
    n = len(panel_clips)
    vf_parts: list[str] = []
    af_parts: list[str] = []

    for i in range(1, n):
        offset += durations[i - 1] - crossfade_s
        vout = f"[v{i}]" if i < n - 1 else "[vout]"
        aout = f"[a{i}]" if i < n - 1 else "[aout]"
        vf_parts.append(
            f"{prev}[{i}:v]xfade=transition=fade:duration={crossfade_s}:offset={offset:.2f}{vout}"
        )
        af_parts.append(
            f"{aprev}[{i}:a]acrossfade=d={crossfade_s}{aout}"
        )
        prev  = vout
        aprev = aout

    full_filter = ";".join(vf_parts + af_parts)

    _ffmpeg(
        *input_args,
        "-filter_complex", full_filter,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        str(out_path),
    )


# ── Pipeline class ────────────────────────────────────────────────────────────

class StoryVideoPipeline(PipelineRun):
    pipeline = "story_video"
    publish_platforms = ("tiktok", "instagram", "youtube_shorts")

    async def execute(self) -> tuple[str, dict]:
        topic = self.params.get("topic", "").strip()
        style = str(self.params.get("style", "educational"))
        if not topic:
            raise ValueError("topic is required")

        slug    = slugify(topic)
        out_dir = OUTPUTS / "story" / slug
        out_dir.mkdir(parents=True, exist_ok=True)

        # 1. Script
        await self.set_stage("script", 15)
        await self.emit("writer", "act", f"Scripting 5-panel story: {topic!r}")
        panels = await _generate_script(topic, style)

        script_path = out_dir / "script.json"
        script_path.write_text(json.dumps(panels, indent=2), encoding="utf-8")

        # 2. Render panels
        await self.set_stage("visuals", 35)
        await self.emit("designer", "act", "Rendering story panels with Pillow")
        img_paths: list[Path] = []
        for i, panel in enumerate(panels):
            dest = out_dir / f"panel_{i+1:02d}.png"
            _render_panel(panel, i + 1, len(panels), dest)
            if dest.exists() and dest.stat().st_size > 0:
                img_paths.append(dest)
            else:
                raise RuntimeError(f"panel {i+1} render failed")

        # 3. TTS narration
        await self.set_stage("audio", 60)
        await self.emit("narrator", "act", "Synthesizing narration via gTTS")
        audio_paths: list[Path | None] = []
        for i, panel in enumerate(panels):
            aud = out_dir / f"narration_{i+1:02d}.mp3"
            ok  = _tts_panel(panel["narration"], aud)
            audio_paths.append(aud if ok else None)
            if not ok:
                await self.emit("narrator", "warn",
                                f"TTS failed for panel {i+1}; will use silence")

        # 4. ffmpeg assembly
        await self.set_stage("assembly", 80)
        await self.emit("editor", "act", "Assembling video with ffmpeg crossfades")
        video_out = out_dir / "video.mp4"
        _assemble_video(panels, img_paths, audio_paths, video_out)

        if not video_out.exists() or video_out.stat().st_size == 0:
            raise RuntimeError("ffmpeg assembly produced empty video")

        # 5. Track assets
        self.track_asset("video", str(video_out), caption=topic,
                         tags=["story_video", slug])
        self.track_asset("text",  str(script_path), caption="script",
                         tags=["script", slug])
        for p in img_paths:
            self.track_asset("image", str(p), caption=topic, tags=["panel", slug])

        await self.set_stage("assembly", 100)
        return str(video_out), {
            "slug":       slug,
            "out_dir":    str(out_dir),
            "panels":     len(panels),
            "video_size": video_out.stat().st_size,
        }


async def run(params: dict) -> dict:
    res = await StoryVideoPipeline(params).run()
    return res.__dict__
