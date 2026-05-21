# brainstorm: build-simo-organs

## Goal
Port core content creation agents from JARVIS to Simo, implementing them as robust, self-correcting agents.

## What I already know
- Agents to port: `channel_spy.py`, `content_factory.py`, `cinema_director.py`, `shorts_agent.py`, `fal_studio.py`, `media_lab.py`, etc.
- Foundation: `simo/backend/agents` directory exists.
- Reliability Requirement: Must implement self-correction loops for each agent.

## Open Questions
- Since there are many agents, which agent should be our "pilot" to establish the self-correction pattern we will then apply to all others?
    1. **`media_lab.py`**: Handles media processing (download/transcription)—highly prone to external failures, perfect for testing self-correction.
    2. **`content_factory.py`**: Handles script generation (LLM calls)—crucial to get right.
    3. **`fal_studio.py`**: Handles image/video gen (API calls)—good for testing fallback logic.

## Requirements
- Port selected agents to `simo/backend/agents/`.
- Implement self-correction loops for porting.

## Acceptance Criteria
- [ ] Pilot agent ported and self-correcting.
- [ ] Pattern defined for remaining agents.

## Technical Notes
- Backend: FastAPI/Python.
- Core Focus: Agentic Engineering (Reliability, Self-Correction).
