"""Layer 2a — Script & Content Skill.

LLM-powered script generation with tone, language, and length controls.
Outputs structured segments: intro, body sections, outro.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from skills.llm_client import LocalLLMClient


SYSTEM_PROMPT = """You are a professional video scriptwriter. Given a topic, tone, language, and target duration,
write a structured video script with the following JSON format:

{
  "title": "Video Title",
  "segments": [
    {"id": "intro", "text": "Opening narration text", "duration_hint": 10},
    {"id": "section_1", "text": "Main point narration", "duration_hint": 20},
    {"id": "section_2", "text": "Supporting point narration", "duration_hint": 20},
    {"id": "outro", "text": "Closing narration", "duration_hint": 10}
  ],
  "speaker_notes": "Full speaker notes for DOCX export",
  "shot_list": ["Wide establishing shot", "Close-up on data", "Medium presenter shot"]
}

Rules:
- Total text should match the requested duration at ~130 words per minute
- Tone must match the requested tone exactly
- Language must match the requested language exactly
- Each segment should be a complete thought that maps to a visual
- Return ONLY valid JSON, no markdown fences
"""


class ScriptContentSkill:
    def __init__(self, config: dict):
        self.config = config
        self.llm = LocalLLMClient(config)

    def generate(self, request) -> dict:
        prompt = self._build_prompt(request)
        raw = self.llm.chat(system=SYSTEM_PROMPT, user=prompt)

        parsed = self._parse_response(raw)
        if not parsed.get("ok"):
            return parsed

        # Save speaker notes as DOCX if skill available
        if parsed.get("speaker_notes"):
            self._save_docx(parsed["speaker_notes"], request)

        return parsed

    def _build_prompt(self, request) -> str:
        duration_min = request.duration_seconds / 60
        word_target = int(duration_min * 130)
        return (
            f"Topic: {request.topic}\n"
            f"Tone: {request.tone}\n"
            f"Language: {request.language}\n"
            f"Target duration: {request.duration_seconds}s (~{word_target} words)\n"
            f"Write the full video script."
        )

    def _parse_response(self, raw: str) -> dict:
        try:
            # Strip markdown fences if present
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            data = __import__("json").loads(cleaned)
            return {"ok": True, "script": data, "segments": data.get("segments", []), "speaker_notes": data.get("speaker_notes", ""), "shot_list": data.get("shot_list", []), "title": data.get("title", "Untitled")}
        except Exception as e:
            return {"ok": False, "error": f"Script parse failed: {e}", "raw": raw[:500]}

    def _save_docx(self, notes: str, request):
        try:
            from skills.docx_writer import write_speaker_notes
            out_dir = Path(self.config["output"]["output_dir"]) / "scripts"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{request.topic[:40].replace(' ', '_')}_notes.docx"
            write_speaker_notes(notes, str(out_path), title=request.topic)
        except ImportError:
            pass  # DOCX skill not available
