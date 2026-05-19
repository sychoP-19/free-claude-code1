"""pipelines/longform.py — long-form video (5-10 min) from a topic."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import httpx

from core.composer import Clip, VideoComposition, generate_thumbnail
from pipelines.base import PipelineRun, OUTPUTS, build_system_prompt, slugify
from pipelines.llm import chat


class LongformPipeline(PipelineRun):
    pipeline = "longform"
    publish_platforms = ("youtube",)

    async def execute(self) -> tuple[str, dict]:
        topic   = self.params.get("topic", "").strip()
        target  = int(self.params.get("length_min", 6))
        if not topic:
            raise ValueError("topic is required")
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg not found on PATH")

        slug = slugify(topic)
        out_dir = OUTPUTS / "longform" / slug
        out_dir.mkdir(parents=True, exist_ok=True)

        # 1. Outline
        await self.set_stage("research", 5)
        await self.emit("strategist", "act", f"Outlining '{topic}' for {target} min")
        outline = await self._outline(topic, target)
        chapters = outline.get("chapters") or []
        if not chapters:
            raise RuntimeError("outline produced no chapters")

        # 2. Per-chapter script + b-roll prompt + narration text
        await self.set_stage("script", 20)
        await self.emit("writer", "act", f"Writing {len(chapters)} chapter scripts")
        for idx, ch in enumerate(chapters):
            ch_script = await self._chapter_script(topic, ch)
            ch["script"] = ch_script

        # 3. B-roll images
        await self.set_stage("visuals", 45)
        await self.emit("designer", "act", "Generating b-roll via Pollinations")
        async with httpx.AsyncClient(timeout=60) as client:
            for idx, ch in enumerate(chapters):
                img_path = out_dir / f"broll_{idx+1:02d}.jpg"
                ok = await self._pollinations(client, ch.get("visual") or ch["title"], img_path, w=1920, h=1080)
                ch["image"] = str(img_path) if ok else ""
        valid_imgs = [ch for ch in chapters if ch.get("image")]
        if not valid_imgs:
            raise RuntimeError("Pollinations failed for every chapter")

        # 4. Narration per chapter
        await self.set_stage("audio", 65)
        await self.emit("writer", "act", "Narrating with gTTS")
        for idx, ch in enumerate(chapters):
            mp3 = out_dir / f"narration_{idx+1:02d}.mp3"
            self._gtts(ch["script"], mp3)
            ch["audio"] = str(mp3) if mp3.exists() and mp3.stat().st_size > 1024 else ""
        if not any(ch.get("audio") for ch in chapters):
            raise RuntimeError("gTTS produced no audio")

        # 5. Assemble with VideoComposition
        await self.set_stage("assembly", 85)
        await self.emit("publisher", "act", "Assembling with VideoComposition")
        video_path = out_dir / "video.mp4"
        thumb_path = out_dir / "thumbnail.png"
        render_result = await self._assemble(chapters, video_path)
        if not render_result["ok"]:
            raise RuntimeError(f"VideoComposition render failed: {render_result['error']}")
        if not video_path.exists() or video_path.stat().st_size < 100_000:
            raise RuntimeError(f"final video too small: {video_path.stat().st_size if video_path.exists() else 0} bytes")
        # Generate thumbnail
        thumb_str = await generate_thumbnail(str(video_path), timestamp=2.0)
        if thumb_str and Path(thumb_str) != thumb_path:
            shutil.copy2(thumb_str, thumb_path)

        # 6. Description + chapters file
        (out_dir / "description.txt").write_text(outline.get("description", topic), encoding="utf-8")
        chapters_txt = self._chapters_text(chapters)
        (out_dir / "chapters.txt").write_text(chapters_txt, encoding="utf-8")

        # Track assets
        for ch in chapters:
            if ch.get("image"): self.track_asset("image", ch["image"], caption=ch["title"], tags=["broll", slug])
            if ch.get("audio"): self.track_asset("audio", ch["audio"], caption=ch["title"], tags=["narration", slug])
        self.track_asset("video", str(video_path), caption=topic, tags=["longform", slug])
        if thumb_path.exists(): self.track_asset("image", str(thumb_path), caption="thumbnail", tags=["thumbnail", slug])

        await self.set_stage("assembly", 100)
        return str(video_path), {"slug": slug, "chapters": len(chapters), "out_dir": str(out_dir)}

    async def _outline(self, topic: str, target_min: int) -> dict:
        prompt = (
            f"Create a structured outline for a {target_min}-minute YouTube video about: {topic}.\n"
            f"Return JSON: {{ \"description\": \"...\", \"chapters\": ["
            f" {{\"title\": \"intro\", \"visual\": \"image prompt\", \"seconds\": 30}}, ... ] }}.\n"
            f"Include intro, {max(3, target_min - 2)} content chapters, and outro. "
            f"Total seconds should sum to ~{target_min * 60}."
        )
        try:
            reply = await chat(
                [{"role": "user", "content": prompt}],
                system=build_system_prompt("strategist"),
                max_tokens=800, run_id=self.run_id,
            )
            m = re.search(r"\{.*\}", reply, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception:
            pass
        # Fallback skeleton
        return {
            "description": topic,
            "chapters": [
                {"title": "Introduction",   "visual": f"cinematic establishing shot of {topic}", "seconds": 30},
                {"title": "Main Concept",   "visual": f"infographic about {topic}",              "seconds": 90},
                {"title": "Deep Dive",      "visual": f"detailed visualization of {topic}",      "seconds": 120},
                {"title": "Real Examples",  "visual": f"real-world examples of {topic}",         "seconds": 90},
                {"title": "Conclusion",     "visual": f"inspiring montage about {topic}",        "seconds": 30},
            ],
        }

    async def _chapter_script(self, topic: str, ch: dict) -> str:
        seconds = int(ch.get("seconds", 60))
        prompt = (
            f"Write the narration for a {seconds}-second chapter titled '{ch.get('title')}' "
            f"in a video about {topic}. Conversational tone. No filler. No hashtags. "
            f"Roughly {max(1, seconds // 6)} sentences."
        )
        try:
            return await chat(
                [{"role": "user", "content": prompt}],
                system=build_system_prompt("writer"),
                max_tokens=400, run_id=self.run_id,
            )
        except Exception as e:
            return f"This chapter explores {ch.get('title')} in the context of {topic}. ({e})"

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

    def _gtts(self, text: str, dest: Path) -> None:
        try:
            from gtts import gTTS
            gTTS(text=text or "...", lang="en", slow=False).save(str(dest))
        except Exception:
            pass

    async def _assemble(self, chapters: list[dict], video_dest: Path) -> dict:
        clips = []
        for ch in chapters:
            img = ch.get("image")
            aud = ch.get("audio")
            if not img:
                continue
            clips.append(Clip(
                image_path=img,
                audio_path=aud or None,
                duration=float(ch.get("seconds", 30)),
                text=ch.get("title") or None,
                text_position="bottom",
                text_size=36,
                text_color="white",
            ))
        if not clips:
            raise RuntimeError("no playable clips assembled")
        composition = VideoComposition(
            clips=clips,
            width=1920,
            height=1080,
            fps=30,
            output_path=str(video_dest),
        )
        return await composition.render()

    def _chapters_text(self, chapters: list[dict]) -> str:
        out = []
        running = 0.0
        for ch in chapters:
            mins, secs = divmod(int(running), 60)
            out.append(f"{mins:02d}:{secs:02d} {ch.get('title','Chapter')}")
            running += float(ch.get("seconds", 30))
        return "\n".join(out)


async def run(params: dict) -> dict:
    res = await LongformPipeline(params).run()
    return res.__dict__
