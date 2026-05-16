"""Layer 2a - Fruit Crusaders Script & Content Skill.

LLM-powered script generation with tone, language, and length controls.
Outputs structured segments for a cinematic anime trailer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from skills.llm_client import LocalLLMClient


FRUIT_CRUSADERS_SYSTEM_PROMPT = """You are a professional anime scriptwriter specializing in epic fantasy anime narratives.
Create a 3-act cinematic trailer script for "Fruit Crusaders: Shattered Hearts" with the following structure:

{
  "title": "Fruit Crusaders: Shattered Hearts - Official Trailer",
  "segments": [
    {
      "id": "intro",
      "text": "In a cosmic storm, the Cherry Twins face a mysterious threat. A brilliant flash of light reveals an ancient power...",
      "duration_hint": 15
    },
    {
      "id": "act1",
      "text": "The Calm Before the Storm: Our heroes live in peaceful harmony, unaware of the cosmic forces that stir in the shadows.",
      "duration_hint": 20
    },
    {
      "id": "transformation",
      "text": "Awakening the Champions: The ancient fruits rise, their chibi forms dissolving as brilliant light reveals their true power!",
      "duration_hint": 30
    },
    {
      "id": "climax",
      "text": "The Final Battle: In the heart of the storm, the fruits face the void creatures in an epic clash of light and darkness!",
      "duration_hint": 30
    },
    {
      "id": "outro",
      "text": "As the storm clears, the champions return to their peaceful forms. But in the distance, a new threat stirs...",
      "duration_hint": 15
    }
  ],
  "speaker_notes": "Fruit Crusaders: Shattered Hearts is an epic fantasy anime where chibi fruit characters transform into powerful humanoid forms to battle cosmic threats. The story follows the journey of the Cherry Twins, Cryo Knight, Citrus Samurai, Durian Tank, and Passion Pirate as they face an ancient void threat.",
  "shot_list": [
    "Wide establishing shot of cosmic storm",
    "Close-up on Cherry Twins' transformation",
    "Epic wide shot of champions gathering light",
    "Action sequence of void creature battle",
    "Emotional close-up of hero's determination",
    "Final wide shot with ominous new threat"
  ]
}

Tone: epic cinematic anime trailer
Language: en
Target duration: 180s (~390 words)
Write the full cinematic trailer script for our anime "Fruit Crusaders: Shattered Hearts" with the character transformations and epic battle sequences.
"""

class FruitCrusadersContentSkill:
    def __init__(self, config: dict):
        self.config = config
        self.llm = LocalLLMClient(config)

    def generate(self, request) -> dict:
        prompt = self._build_prompt(request)
        raw = self.llm.chat(system=FRUIT_CRUSADERS_SYSTEM_PROMPT, user=prompt)

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
            f"Tone: epic cinematic anime trailer\n"
            f"Language: {request.language}\n"
            f"Target duration: {request.duration_seconds}s (~{word_target} words)\n"
            f"Write the full cinematic trailer script for our anime \"{request.topic}\" with the character transformations and epic battle sequences."
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