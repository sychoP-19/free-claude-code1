"""Model override logic for dual-brain routing.

Applies the classified brain target to the request model.
"""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import Settings
from .intent_classifier import BrainTarget


@dataclass(frozen=True, slots=True)
class ModelOverrideResult:
    """Result of applying a model override."""

    original_model: str
    overridden_model: str | None
    brain_target: BrainTarget
    applied: bool


class ModelOverrideApplier:
    """Applies model overrides based on brain target classification."""

    def __init__(self, settings: Settings):
        self._settings = settings

    def apply(self, original_model: str, brain_target: BrainTarget) -> ModelOverrideResult:
        """Apply model override for the given brain target.

        Args:
            original_model: The incoming request's model name.
            brain_target: The classified brain target (CODEX, CLAUDE, or AUTO).

        Returns:
            ModelOverrideResult with the (potentially) overridden model.
        """
        if not getattr(self._settings, "dual_brain_enabled", False):
            return ModelOverrideResult(
                original_model=original_model,
                overridden_model=None,
                brain_target=brain_target,
                applied=False,
            )

        match brain_target:
            case BrainTarget.CODEX:
                codex_model = self._settings.dual_brain_codex_model
                if codex_model and codex_model != original_model:
                    return ModelOverrideResult(
                        original_model=original_model,
                        overridden_model=codex_model,
                        brain_target=brain_target,
                        applied=True,
                    )
            case BrainTarget.CLAUDE:
                claude_model = self._settings.dual_brain_claude_model
                if claude_model and claude_model != original_model:
                    return ModelOverrideResult(
                        original_model=original_model,
                        overridden_model=claude_model,
                        brain_target=brain_target,
                        applied=True,
                    )
            case BrainTarget.AUTO:
                # No override when in auto mode
                pass

        return ModelOverrideResult(
            original_model=original_model,
            overridden_model=None,
            brain_target=brain_target,
            applied=False,
        )


def maybe_override_model(
    original_model: str, brain_target: BrainTarget, settings: Settings
) -> ModelOverrideResult:
    """Convenience function to apply model override.

    Args:
        original_model: The incoming request's model name.
        brain_target: The classified brain target.
        settings: The application settings.

    Returns:
        ModelOverrideResult with the (potentially) overridden model.
    """
    applier = ModelOverrideApplier(settings)
    return applier.apply(original_model, brain_target)
