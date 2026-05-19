# JARVIS Content Intelligence System — Project Context

## What This Is

JARVIS is a FastAPI + Jinja2 + WebSocket AI content creation dashboard.
It orchestrates multiple AI agents for YouTube content analysis, shorts generation,
trend mining, monetization intelligence, and AI media generation.

## Stack

- **Runtime**: Python 3.12+ with `uv`
- **Framework**: FastAPI + Uvicorn + Jinja2 templates
- **Real-time**: WebSockets (custom `core/websocket_manager.py`)
- **Port**: 8090

## Start Command

```
uv run uvicorn content-creator.app:app --host 0.0.0.0 --port 8090 --reload
```

Run from `C:\Users\Admin\Desktop\free-claude-code\` (the parent of content-creator/).

## Environment Variables

File: `content-creator/.env`

| Variable | Purpose |
|----------|---------|
| FAL_KEY / FAL_API_KEY | FAL.ai image/video generation |
| OLLAMA_BASE_URL | Ollama local LLM (default: http://localhost:11434) |
| GOOGLE_CLIENT_ID | Gmail OAuth |
| GOOGLE_CLIENT_SECRET | Gmail OAuth |
| WHATSAPP_NUMBER | Portfolio contact WhatsApp link |
| PORTFOLIO_SECRET | Guards POST /api/revenue |
| WHISPER_SERVER | Whisper transcription server |
| OPENAI_API_KEY | Optional OpenAI Whisper fallback |

## Agents (in `content-creator/agents/`)

| Agent File | Purpose |
|-----------|---------|
| `channel_spy.py` | YouTube channel analysis |
| `trend_miner.py` | Trend discovery + blueprint generation |
| `content_factory.py` | Script + thumbnail + hashtag generation |
| `monetization_intel.py` | Revenue potential analysis |
| `cinema_director.py` | Video generation pipeline |
| `shorts_agent.py` | YouTube → viral shorts (wraps AI-Youtube-Shorts-Generator) |
| `fal_studio.py` | FAL.ai image + video generation |
| `media_lab.py` | yt-dlp download + Whisper transcription |
| `ollama_agent.py` | Local Ollama LLM chat + content analysis |
| `trending_agent.py` | YouTube RSS trending topics (free, no key) |
| `auto_shorts_agent.py` | Topic → Ollama script → Pollinations images → moviepy video |
| `github_trending_agent.py` | GitHub trending repo discovery |

## Core Utilities (in `content-creator/core/`)

| File | Purpose |
|------|---------|
| `websocket_manager.py` | WebSocket broadcast (log, metric, agent_update) |
| `ollama_client.py` | Ollama API wrapper |
| `downloader.py` | yt-dlp wrapper |
| `video_processor.py` | Output video file management |

## Integrations (in `content-creator/integrations/`)

| File | Purpose |
|------|---------|
| `gmail_client.py` | Gmail OAuth + send notifications |
| `registry.py` | Repo presence checker (fixes startup import) |

## All Pages & Routes

### Pages (GET)
| Route | Template | Purpose |
|-------|----------|---------|
| `/` | dashboard.html | Main JARVIS dashboard |
| `/spy` | spy.html | Channel spy agent |
| `/trends` | trends.html | Trend miner |
| `/factory` | factory.html | Content factory |
| `/money` | money.html | Monetization intel |
| `/director` | director.html | Cinema director |
| `/repos` | repos.html | Repo hub + services status |
| `/shorts` | shorts.html | Shorts generator |
| `/content-hub` | content_hub.html | Content hub |
| `/orchestration` | orchestration.html | Agent orchestration panel |
| `/portfolio` | portfolio.html | Public portfolio + revenue |
| `/ai-studio` | ai_studio.html | FAL.ai image/video gen |
| `/media-lab` | media_lab.html | Download + transcribe |
| `/ollama-studio` | ollama_studio.html | Ollama chat |
| `/command` | command.html | Command center |
| `/revenue` | revenue.html | Revenue tracker |
| `/pipeline` | pipeline.html | Pipeline view |
| `/session` | session.html | Session manager |
| `/github-hub` | github_hub.html | GitHub trending repos |
| `/skills` | skills.html | Content calendar + goals |

### Key API Routes
| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/api/trending/topics` | YouTube trending (RSS) |
| POST | `/api/shorts/auto` | Auto-generate short from topic |
| GET | `/api/github/trending` | GitHub trending repos |
| POST | `/api/github/clone` | Clone a repo to ai-repositories/ |
| POST | `/api/github/install` | Install repo dependencies |
| GET | `/api/repos/services` | Check running services (ports) |
| POST | `/api/agents/shorts/run` | Shorts pipeline (AI-YT-Shorts-Gen) |
| POST | `/api/agents/fal/image` | FAL image generation |
| POST | `/api/agents/fal/video` | FAL video generation |
| GET | `/api/fal/status` | FAL key connected? |
| POST | `/api/agents/spy/run` | Channel spy |
| POST | `/api/agents/trends/run` | Trend mining |
| POST | `/api/agents/factory/run` | Content factory |
| POST | `/api/agents/money/run` | Monetization scan |
| POST | `/api/agents/director/run` | Cinema director |
| POST | `/api/media/download` | yt-dlp download |
| POST | `/api/media/transcribe` | Whisper transcription |
| POST | `/api/media/analyze` | Ollama content analysis |
| GET | `/api/ollama/models` | List Ollama models |
| POST | `/api/ollama/chat` | Ollama chat |
| GET | `/api/github/trending` | GitHub trending |
| GET | `/api/gmail/status` | Gmail connected? |
| GET | `/api/revenue` | Revenue data |
| POST | `/api/revenue` | Update revenue (auth: X-Portfolio-Secret) |
| POST | `/api/contact` | Portfolio contact form |
| WebSocket | `/ws` | Real-time agent events |

## External Integrations

| Service | URL | Key Required |
|---------|-----|-------------|
| FAL.ai | https://fal.run | FAL_KEY (in .env) |
| Ollama | http://localhost:11434 | None (local) |
| Free proxy (Claude) | http://localhost:8082 | None (local) |
| Pollinations.ai | https://image.pollinations.ai | None (free) |
| YouTube RSS | https://www.youtube.com/feeds/... | None (free) |
| GitHub API | https://api.github.com | None (60/hr) |

## AI Repos (in `C:\Users\Admin\Desktop\free-claude-code\ai-repositories\`)

| Repo | Port | Purpose |
|------|------|---------|
| AI-Youtube-Shorts-Generator | — | Shorts pipeline (already integrated) |
| Pixelle-Video | 7861 | Video generation (Streamlit) |
| ComfyUI | 8188 | Stable Diffusion frontend |
| stable-diffusion-webui | 7860 | SD web UI |
| TTS | — | Coqui TTS voice synthesis |
| n8n-mcp | 5678 | Workflow automation |
| yt-dlp | — | Video downloader (already integrated) |

## Frontend Patterns

- **No innerHTML with dynamic data** — always use `createElement` / `textContent` / `appendChild`
- WebSocket events: `{type: "log"|"metric"|"agent_update", ...}` received by every page via `base.html`
- Dark glass JARVIS UI: CSS variables in `static/css/jarvis.css`
- Sidebar nav active state: `{% set active = "page_name" %}` in each template

## Voice Interface

- `static/js/voice.js` — `Voice` module, exposed as `window.jarvisVoice`
- Web Speech API: `SpeechRecognition` (input, `recognition.lang` switchable) + `SpeechSynthesis` (output)
- Languages: English (`en-US`), Arabic (`ar-SA`), Moroccan Darija (`ar-MA`)
- Auto-detect Arabic from Unicode range `/[؀-ۿ]/`, picks `ar-SA` voice automatically
- Language toggle `<select id="jarvis-lang-select">` in topbar calls `Voice.setLang(lang)`
- Pitch 0.85, rate 0.92 for JARVIS robotic tone
- Mic button `id="voice-btn"` in base.html topbar; `.listening` CSS class animates when active

## Chat Overlay

- `static/js/chat-overlay.js` — floating panel, bottom-right, built from `ChatOverlay` module
- Tries `POST http://localhost:8082/v1/messages` (free-claude-code Claude proxy) first
- Falls back to `POST /api/ollama/chat` if proxy offline or errors
- Both paths call `Voice.speak(reply)` for audio output after receiving response
- System prompt: multilingual JARVIS assistant for content strategy and YouTube

## Standalone Free Mode

- `content-creator/JARVIS.html` — open directly in browser, no server needed
- Contains: FAL.ai image gen, FREE Pollinations image gen (no key), Ollama chat, gallery, universe presets
- Pollinations URL pattern: `https://image.pollinations.ai/prompt/{encoded}?model={m}&width={w}&height={h}&seed={s}&nologo=true&enhance=true`
- Models: flux, flux-realism, flux-anime, flux-3d, turbo, dreamshaper, any-dark

## What Was Built (May 2026 Session)

Files created/updated this session:
- `integrations/registry.py` — fixes JARVIS startup crash (was missing, causing import error)
- `agents/trending_agent.py` — YouTube RSS trending, 20 topics, fallback list
- `agents/auto_shorts_agent.py` — topic→Ollama→Pollinations→gTTS→moviepy video pipeline
- `agents/github_trending_agent.py` — GitHub Search API, clone/install repos safely (list args)
- `templates/github_hub.html` — GitHub trending browser with clone/install buttons
- `templates/skills.html` — 3-tab dashboard: content calendar, revenue goals, trend alerts
- `static/js/voice.js` — rewritten with Arabic/Darija support and `jarvisVoice` global
- `static/js/chat-overlay.js` — added Ollama fallback when proxy is offline
- `templates/base.html` — added GitHub Hub + Skills nav links, language toggle in topbar
- `templates/repos.html` — added Running Services panel (parallel port checks)
- `requirements.txt` — added gTTS>=2.5.1, moviepy>=1.0.3
- `JARVIS.html` — added Pollinations free image gen tab

New API routes added to `app.py`:
- `GET /github-hub`, `GET /skills` — page routes
- `GET /api/trending/topics` — YouTube RSS
- `POST /api/shorts/auto` — auto video from topic
- `GET /api/github/trending` — GitHub Search API
- `POST /api/github/clone` — clone repo (validates github.com only)
- `POST /api/github/install` — install repo deps with uv
- `GET /api/repos/services` — parallel port check (Ollama/ComfyUI/SD/Pixelle/n8n/Proxy)

## Verification Checklist

Run after any restart:
1. `http://localhost:8090` — dashboard loads (HTTP 200)
2. WebSocket connects (green dot in topbar)
3. Mic button → browser mic permission → speak → text appears in chat
4. Chat → JARVIS responds (English or Arabic) + voice speaks back
5. Language dropdown → switch to AR → speak Arabic → JARVIS replies in Arabic
6. `/api/trending/topics` → JSON with 10+ topics
7. `/api/github/trending` → JSON with repos
8. `/api/repos/services` → JSON with Ollama/proxy status (responds in ~2s)
9. `/github-hub` → trending repos grid loads
10. `/skills` → 3 tabs work (calendar, revenue, alerts)
11. Open `JARVIS.html` directly → Pollinations free image gen works
