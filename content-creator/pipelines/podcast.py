"""pipelines/podcast.py — 2-speaker dialogue → MP3 episode + show notes."""
from __future__ import annotations

import re
from pathlib import Path

from pipelines.base import PipelineRun, OUTPUTS, build_system_prompt, slugify
from pipelines.llm import chat


class PodcastPipeline(PipelineRun):
    pipeline = "podcast"
    publish_platforms = ("spotify", "apple-podcasts")

    async def execute(self) -> tuple[str, dict]:
        topic = self.params.get("topic", "").strip()
        minutes = int(self.params.get("minutes", 5))
        if not topic:
            raise ValueError("topic is required")

        slug = slugify(topic)
        out_dir = OUTPUTS / "podcast" / slug
        out_dir.mkdir(parents=True, exist_ok=True)

        await self.set_stage("script", 15)
        await self.emit("writer", "act", f"Writing {minutes}-min dialogue on '{topic}'")
        dialogue = await self._dialogue(topic, minutes)
        lines = self._parse_dialogue(dialogue)
        if not lines:
            raise RuntimeError("dialogue parsing returned no lines")

        await self.set_stage("audio", 50)
        await self.emit("designer", "act", f"Rendering {len(lines)} TTS lines (HOST en-US / GUEST en-GB)")
        segments = self._render_segments(lines, out_dir)
        if not segments:
            raise RuntimeError("gTTS produced no audio segments")

        await self.set_stage("assembly", 85)
        episode = out_dir / "episode.mp3"
        self._stitch(segments, episode)
        if not episode.exists() or episode.stat().st_size < 5000:
            raise RuntimeError("final episode mp3 too small")

        # Show notes
        notes = out_dir / "shownotes.md"
        notes.write_text(self._shownotes(topic, dialogue), encoding="utf-8")

        self.track_asset("audio", str(episode), caption=topic, tags=["podcast", slug])
        self.track_asset("text",  str(notes),   caption="show notes", tags=["notes", slug])

        await self.set_stage("assembly", 100)
        return str(episode), {"slug": slug, "lines": len(lines), "out_dir": str(out_dir)}

    async def _dialogue(self, topic: str, minutes: int) -> str:
        prompt = (
            f"Write a {minutes}-minute podcast dialogue between HOST and GUEST on: {topic}.\n"
            f"Format STRICTLY as alternating lines like:\n"
            f"HOST: ...\nGUEST: ...\n\n"
            f"Around {minutes * 12} lines total. Natural, conversational, with specific insights."
        )
        return await chat(
            [{"role": "user", "content": prompt}],
            system=build_system_prompt("writer"),
            max_tokens=2000, run_id=self.run_id,
        )

    def _parse_dialogue(self, text: str) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for line in text.splitlines():
            line = line.strip()
            m = re.match(r"^(HOST|GUEST)\s*:\s*(.+)$", line, re.IGNORECASE)
            if m:
                out.append((m.group(1).upper(), m.group(2).strip()))
        return out

    def _render_segments(self, lines: list[tuple[str, str]], out_dir: Path) -> list[Path]:
        try:
            from gtts import gTTS
        except ImportError:
            raise RuntimeError("gTTS not installed")
        segs: list[Path] = []
        for i, (who, text) in enumerate(lines):
            tld = "com" if who == "HOST" else "co.uk"  # en-US vs en-GB pacing
            p = out_dir / f"seg_{i:03d}_{who.lower()}.mp3"
            try:
                gTTS(text=text, lang="en", tld=tld, slow=False).save(str(p))
                if p.exists() and p.stat().st_size > 200:
                    segs.append(p)
            except Exception:
                continue
        return segs

    def _stitch(self, segments: list[Path], dest: Path) -> None:
        # Simple binary concatenation of MP3 frames works well enough for gTTS-only
        # output. For sample-accurate stitching we'd need ffmpeg, but this keeps
        # the dependency surface small.
        with open(dest, "wb") as out:
            for s in segments:
                out.write(s.read_bytes())

    def _shownotes(self, topic: str, dialogue: str) -> str:
        return (
            f"# {topic}\n\n"
            f"Auto-generated podcast episode.\n\n"
            f"## Transcript\n\n```\n{dialogue}\n```\n"
        )


async def run(params: dict) -> dict:
    res = await PodcastPipeline(params).run()
    return res.__dict__
