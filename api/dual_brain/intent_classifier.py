"""Intent classifier for dual-brain routing.

Classifies incoming requests as either codex-brain (fast code generation)
or claude-brain (deep reasoning, review, architecture).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

# Keywords that signal codex-brain tasks (fast code generation)
CODEX_KEYWORDS = frozenset(
    {
        "write",
        "implement",
        "code",
        "function",
        "class",
        "create",
        "generate",
        "build",
        "script",
        "refactor",
        "add",
        "fix bug",
        "add test",
        "unit test",
        "test file",
    }
)

# Keywords that signal claude-brain tasks (deep reasoning, review, architecture)
CLAUDE_KEYWORDS = frozenset(
    {
        "review",
        "architecture",
        "design",
        "plan",
        "security",
        "audit",
        "assess",
        "evaluate",
        "analyze",
        "reason",
        "explain",
        "why",
        "tradeoff",
        "pattern",
        "strategy",
        "orchestration",
        "orchestrate",
        "brainstorm",
        "tdd",
        "test-driven",
        "pair program",
        "pair-program",
    }
)


class BrainTarget(str, Enum):
    """Target brain for a given request."""

    CODEX = "codex"
    CLAUDE = "claude"
    AUTO = "auto"


def classify_intent(
    messages: list[dict[str, Any]],
    system: str | None = None,
) -> BrainTarget:
    """Classify incoming request as codex or claude brain target.

    Returns:
        BrainTarget: The target brain for the request.

    Strategy:
        1. Flatten all text (system + messages) to lower case
        2. Count keyword matches for codex vs claude
        3. Return BrainTarget with highest score, defaulting to AUTO (no override)
    """
    flat = ""
    if system:
        flat += system.lower() + " "
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            flat += content.lower() + " "
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and "text" in part:
                    flat += part["text"].lower() + " "

    # Count matches
    codex_score = sum(1 for kw in CODEX_KEYWORDS if kw in flat)
    claude_score = sum(1 for kw in CLAUDE_KEYWORDS if kw in flat)

    # Default: no clear signal → let the model router handle it
    if codex_score == 0 and claude_score == 0:
        return BrainTarget.AUTO

    if codex_score >= claude_score:
        return BrainTarget.CODEX
    return BrainTarget.CLAUDE
