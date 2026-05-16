# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

## Agent Skills

### Issue tracker
Local markdown — issues tracked under `.scratch/<feature>/ISSUE.md`. See `docs/agents/issue-tracker.md`.

### Triage labels
Uses five canonical labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs
Single-context layout. Core domains: AI proxy server + JobAgent Pro. See `docs/agents/domain.md`.