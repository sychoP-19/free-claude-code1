# Update to Gemini 3.5 Flash & Comprehensive Model Inventory

## Goal

1. Update the project configuration and gateway to support the newly released Gemini 3.5 Flash model (GA May 19, 2026).
2. Refresh the `GATEWAY_MODELS` list to include a comprehensive set of "working" models from OpenRouter and NVIDIA NIM, ensuring they appear when the user types `/model` (or `models`).
3. Ensure the `/model` command displays all possible available working models as requested by the user.

## What I already know

*   Gemini 3.5 Flash is Generally Available (GA) as of May 19, 2026.
*   The current `.env` uses `open_router/google/gemini-2.5-flash` for `MODEL_HAIKU`.
*   The `GATEWAY_MODELS` list in `.env` currently includes a manually curated list.
*   The project uses a custom proxy that maps Claude-style model names to provider models via `.env` settings.
*   The OpenRouter model ID for Gemini 3.5 Flash is `google/gemini-3.5-flash`.
*   The system supports automated model discovery via the `ProviderRegistry` (seen in `api/routes.py`).

## Assumptions (temporary)

*   The OpenRouter model ID for Gemini 3.5 Flash is `google/gemini-3.5-flash`.
*   The user wants the `GATEWAY_MODELS` list to be updated with the latest frontier models (GPT-5, Claude 4, etc. as seen in the `.env` snippet).

## Open Questions

*   None (Blocking).

## Requirements (evolving)

*   Update `MODEL_HAIKU` in `.env` to `open_router/google/gemini-3.5-flash`.
*   Refresh `GATEWAY_MODELS` in `.env` with a curated, high-quality list of modern frontier models from OpenRouter and NVIDIA NIM.
*   Verify that Gemini 3.5 Flash and other new models appear in the `/model` list and route correctly.

## Decision (ADR-lite)

**Context**: The user wants all "working" models to be available.
**Decision**: Option 1 (Curated Expansion). We will manually curate a list of ~20 high-quality frontier models in `.env` rather than listing every single model available on the providers.
**Consequences**: The list stays relevant and verified "working," but requires manual updates when new major models are released.

## Acceptance Criteria (evolving)

*   [ ] `.env` file updated with Gemini 3.5 Flash and other latest frontier models.
*   [ ] Gemini 3.5 Flash appears in the `/model` discovery list.
*   [ ] The model list shown by the proxy is significantly expanded and verified to be "working".
*   [ ] A test request to `claude-3-haiku-20240307` is routed to Gemini 3.5 Flash.

## Definition of Done (team quality bar)

*   Tests added/updated (unit/integration where appropriate)
*   Lint / typecheck / CI green
*   Docs/notes updated if behavior changes
*   Rollout/rollback considered if risky

## Out of Scope (explicit)

*   Updating to Gemini 3.5 Pro (unless requested).
*   Changes to the core routing logic (unless required by the new model).

## Technical Notes

*   Files impacted: `.env`
*   Current `MODEL_HAIKU`: `open_router/google/gemini-2.5-flash`
*   Current `GATEWAY_MODELS`: includes `open_router/google/gemini-2.5-pro`, `open_router/google/gemini-2.5-flash`
