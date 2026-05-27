"""Service for rebuilding prompts based on Karpathy guidelines."""

from __future__ import annotations

from loguru import logger

from api.models.anthropic import Message, MessagesRequest
from config.settings import Settings
from core.anthropic import extract_text_from_content
from providers.base import BaseProvider

_KARPATHY_GUIDELINES = """\
1. Think Before Coding — State assumptions explicitly. If uncertain, ask. Multiple interpretations → present them, don't pick silently.
2. Simplicity First — Minimum code that solves the problem. Nothing speculative. No features beyond what was asked.
3. Surgical Changes — Touch only what you must. Don't refactor things that aren't broken. Match existing style.
4. Goal-Driven Execution — Define success criteria. Transform tasks into verifiable goals. Loop until verified.
5. No Abstractions for Single-Use Code — If it could be 50 lines instead of 200, rewrite it. No premature generalization."""

_REBUILD_CONSTRAINTS = """\
Prompt Constraints:
- Maintain technical markers (like command prefixes).
- Apply Karpathy-style simplicity: prune filler, surface assumptions.
- Ensure goal-driven execution in every rebuilt prompt."""


class PromptRebuilder:
    def __init__(self, settings: Settings, provider_getter: callable):
        self._settings = settings
        self._provider_getter = provider_getter

    async def rebuild(self, request_data: MessagesRequest) -> MessagesRequest:
        logger.info("Rebuilding prompt using LLM agent.")

        original_prompt = ""
        for msg in request_data.messages:
            if msg.role == "user":
                text = extract_text_from_content(msg.content)
                if text.strip().upper().startswith("REBUILD:"):
                    original_prompt = text.strip()[len("REBUILD:"):].strip()
                    break

        if not original_prompt:
            return request_data

        new_system = (
            f"{request_data.system or ''}\n\n"
            f"# Mandatory Behavioral Guidelines\n{_KARPATHY_GUIDELINES}\n\n"
            f"# {_REBUILD_CONSTRAINTS}\n\n"
            "Rebuild the following prompt according to these guidelines. "
            "Return only the rebuilt prompt text."
        )

        provider_id = self._settings.model.split("/")[0]
        provider: BaseProvider = self._provider_getter(provider_id)
        rebuild_request = MessagesRequest(
            model=self._settings.model,
            messages=[Message(role="user", content=f"Rebuild this: {original_prompt}")],
            system=new_system,
        )

        rebuilt_text = ""
        async for chunk in provider.stream_response(
            rebuild_request, input_tokens=0, request_id="rebuild", thinking_enabled=False,
        ):
            rebuilt_text += chunk

        # Return a NEW MessagesRequest — never mutate the original.
        new_messages = []
        for msg in request_data.messages:
            if msg.role == "user" and msg is not None:
                text = extract_text_from_content(msg.content)
                if text.strip().upper().startswith("REBUILD:"):
                    new_messages.append(Message(role="user", content=rebuilt_text))
                    continue
            new_messages.append(msg)

        return request_data.model_copy(
            update={"messages": new_messages}, deep=True,
        )
