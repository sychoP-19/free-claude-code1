# port-backend-and-integrate-frontend

## Goal
Port core backend agent logic (starting with `ollama_client.py`) and integrate the Flet frontend to connect to the backend WebSocket endpoint.

## Requirements
- Port `content-creator/core/ollama_client.py` to `simo/backend/ollama_client.py`.
- Update `simo/frontend/main.py` to connect to `ws://localhost:8091/ws` and display updates.

## Acceptance Criteria
- [ ] `ollama_client.py` ported and tested.
- [ ] Flet frontend connects to backend WebSocket.
- [ ] UI displays WebSocket connection status or logs.

## Definition of Done
- Tests added.
- Lint/typecheck green.
