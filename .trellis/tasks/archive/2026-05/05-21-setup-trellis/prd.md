# brainstorm: setup-trellis-and-check-hooks

## Goal
Implement Trellis in the Claude environment and investigate/fix any hook errors.

## What I already know
- Trellis is installed in the project.
- Hooks exist in `.gemini/hooks`: `inject-workflow-state.py` and `session-start.py`.
- User wants Trellis implemented in Claude (might mean configuring Claude to use Trellis commands/skills).

## Assumptions (temporary)
- Hooks are working but user suspects errors.
- Trellis is not fully integrated/configured in Claude's configuration or settings.

## Open Questions
- What exactly do you mean by "implement [Trellis] in my claude"? (e.g., install skills, configure settings?)
- Are you seeing specific error messages related to hooks?

## Requirements (evolving)
- Investigate hooks for errors.
- Configure Claude/Agent settings for Trellis integration.

## Acceptance Criteria (evolving)
- [ ] Hooks verified or fixed.
- [ ] Trellis integrated with Claude/Agent.

## Definition of Done
- Tests added/updated (if applicable).
- Lint / typecheck / CI green.

## Out of Scope
- None.

## Technical Notes
- Hooks: `.gemini/hooks/inject-workflow-state.py`, `.gemini/hooks/session-start.py`
- Claude CLI check: Not found in `package.json` dependencies.
