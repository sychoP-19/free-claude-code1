# AGENTIC DIRECTIVE

> This file is identical to CLAUDE.md. Keep them in sync.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Coding Environment

- Install astral uv: `curl -LsSf https://astral.sh/uv/install.sh | sh` (update if already installed)
- Install Python 3.14: `uv python install 3.14`
- Always use `uv run` to run files instead of global `python`
- Current uv ruff formatter targets py314 (supports multiple exception types without parentheses, except TypeError, ValueError)
- Read `.env.example` for environment variables
- All CI checks must pass; failing checks block merge
- Add tests for new changes (including edge cases), then run `uv run pytest`
- Run checks in order: `uv run ruff format`, `uv run ruff check`, `uv run ty check`, `uv run pytest`
- Do not add `# type: ignore` or `# ty: ignore`; fix the underlying type issue
- All 5 checks are enforced in `tests.yml` on push/merge

## Essential Development Commands

### Standard Workflow Commands
```bash
# Code formatting (run first)
uv run ruff format

# Linting check (run second)
uv run ruff check

# Type checking (run third)
uv run ty check

# Full test suite (run last)
uv run pytest
```

### Targeted Development Commands
```bash
# Run a specific test file
uv run pytest tests/api/test_web_server_tools.py

# Run a specific test function
uv run pytest tests/api/test_web_server_tools.py::test_web_server_tool

# Run tests with coverage reporting
uv run pytest --cov=src --cov-report=term-missing

# Start development server with auto-reload
uv run uvicorn server:app --host 0.0.0.0 --port 8082 --reload

# Initialize CLI tools after installation
uv tool install .
```

### Provider-Specific Testing
```bash
# Run smoke tests against live providers (requires API keys in .env)
uv run pytest smoke/

# Run unit tests only (no external dependencies)
uv run pytest tests/ -m "not smoke"
```

## Architecture Overview

### Core System Components

1. **Provider Abstraction Layer**
   - Two transport implementations:
     * `OpenAIChatTransport`: For NVIDIA NIM and OpenRouter (uses `/chat/completions` endpoint)
     * `AnthropicMessagesTransport`: For DeepSeek, LM Studio, Ollama, and llama.cpp (uses `/messages` endpoint)
   - Provider registry dynamically loads implementations from `config.provider_catalog.PROVIDER_CATALOG`
   - Each provider implements: `stream_response()`, `list_model_ids()`, `list_model_infos()`, `cleanup()`

2. **Protocol Translation Layer** (`core/anthropic/`)
   - `SSEBuilder`: Converts provider responses to Anthropic-compatible Server-Sent Events format
   - `HeuristicToolParser`: Extracts tool calls from OpenAI-style streaming responses
   - `ThinkTagParser`: Detects reasoning blocks (`<thinking>...</thinking>`) for thinking mode support
   - `ContentBlockManager`: Manages accumulation and delta application of streaming content blocks

3. **Request Processing Pipeline**
   ```
   Client Request
         ↓
   api/app.py (Exception handling)
         ↓
   api/routes.py (FastAPI endpoints: /v1/messages, /v1/models, etc.)
         ↓
   ClaudeProxyService (Resolves model ID via get_gateway_model_id())
         ↓
   Provider Selection (From registry based on model routing rules)
         ↓
   provider.stream_response() (Calls appropriate transport)
         ↓
   Protocol Translation (SSE building, tool parsing, thinking detection)
         ↓
   Streamed Response to Client (Anthropic-compatible SSE format)
   ```

4. **Runtime & Configuration**
   - `api/runtime.py`: Manages `AppRuntime` lifecycle (startup/shutdown)
   - Configuration hierarchy: 
     * Primary: `C:/Users/Admin/.config/free-claude-code/.env`
     * Project: `C:/Users/Admin/Desktop/free-claude-code/.env` (overrides primary)
   - Model routing: `claude-sonnet-*`, `claude-opus-*`, `claude-haiku-*` mapped in `config.settings`
   - Tier-specific overrides: `MODEL_OPUS`, `MODEL_SONNET`, `MODEL_HAIKU` environment variables
   - Rate limiting: `GlobalRateLimiter` in `core/rate_limiter.py` (configured via `.env`)

### Key Extension Points

**Adding a New Provider:**
1. Add metadata to `config/provider_catalog.py`:
   ```python
   PROVIDER_CATALOG[ProviderID.NEW_PROVIDER] = {
       "base_url": "https://api.example.com/v1",
       "transport_type": "openai_chat" or "anthropic_messages",
       "capabilities": {"tool_use": True, "thinking": False},
       "credentials": {"api_key": EnvVar.NEW_PROVIDER_API_KEY}
   }
   ```
2. Create provider module in `providers/new_provider/`
3. Implement required methods (`stream_response()`, `list_model_ids()`, etc.)
4. Add provider-specific config to constructor (avoid modifying base `ProviderConfig`)
5. Test with `uv run pytest smoke/test_new_provider.py`

**Modifying Core Functionality:**
- Streaming/SSE handling: `core/anthropic/sse.py`
- Tool call parsing: `core/anthropic/tool_parser.py`
- Thinking/reasoning detection: `core/anthropic/think_parser.py`
- Error handling: `api/app.py` exception handlers
- Rate limiting: `core/rate_limiter.py`

### Directory Structure Significance

- **api/**: HTTP layer (FastAPI routes, service logic, request/response handling)
- **core/**: Shared Anthropic protocol utilities (SSE building, tool parsing, etc.)
- **providers/**: Provider-specific implementations (transports, authentication, model discovery)
- **config/**: Application settings, provider catalog, constants
- **cli/**: Command-line interface and process management utilities
- **messaging/**: Optional integrations (Discord/Telegram bots, voice transcription)
- **tests/**: Unit tests (mock external dependencies for isolation)
- **smoke/**: Live integration tests against real providers (requires valid API keys)
- **workspace/**: Working directory used by messaging platforms for session storage

This architecture enables the proxy to route Claude Code API traffic to various free backends while maintaining protocol compatibility and providing extensibility for new providers.

## Architecture Principles

- **Shared utilities**: Put shared Anthropic protocol logic in neutral `core/anthropic/` modules. Do not have one provider import from another provider's utils.
- **DRY**: Extract shared base classes to eliminate duplication. Prefer composition over copy-paste.
- **Encapsulation**: Use accessor methods for internal state (e.g. `set_current_task()`), not direct `_attribute` assignment from outside.
- **Provider-specific config**: Keep provider-specific fields (e.g. `nim_settings`) in provider constructors, not in the base `ProviderConfig`.
- **Dead code**: Remove unused code, legacy systems, and hardcoded values. Use settings/config instead of literals (e.g. `settings.provider_type` not `"nvidia_nim"`).
- **Performance**: Use list accumulation for strings (not `+=` in loops), cache env vars at init, prefer iterative over recursive when stack depth matters.
- **Platform-agnostic naming**: Use generic names (e.g. `PLATFORM_EDIT`) not platform-specific ones (e.g. `TELEGRAM_EDIT`) in shared code.
- **No type ignores**: Do not add `# type: ignore` or `# ty: ignore`. Fix the underlying type issue.
- **Complete migrations**: When moving modules, update imports to the new owner and remove old compatibility shims in the same change unless preserving a published interface is explicitly required.
- **Maximum Test Coverage**: There should be maximum test coverage for everything, preferably live smoke test coverage to catch bugs early.

## Cognitive Workflow

1. **ANALYZE**: Read relevant files. Do not guess.
2. **PLAN**: Map out the logic. Identify root cause or required changes. Order changes by dependency.
3. **EXECUTE**: Fix the cause, not the symptom. Execute incrementally with clear commits.
4. **VERIFY**: Run CI checks and relevant smoke tests. Confirm the fix via logs or output.
5. **SPECIFICITY**: Do exactly as much as asked; nothing more, nothing less.
6. **PROPAGATION**: Changes impact multiple files; propagate updates correctly.

## Summary Standards

- Summaries must be technical and granular.
- Include: [Files Changed], [Logic Altered], [Verification Method], [Residual Risks] (if no residual risks then say none).

## Agent Skills

### Issue tracker
Local markdown — issues tracked under `.scratch/<feature>/ISSUE.md`. See `docs/agents/issue-tracker.md`.

### Triage labels
Uses five canonical labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs
Single-context layout. Core domains: AI proxy server + JobAgent Pro. See `docs/agents/domain.md`.

## Tools

- Prefer built-in tools (grep, read_file, etc.) over manual workflows. Check tool availability before use.
