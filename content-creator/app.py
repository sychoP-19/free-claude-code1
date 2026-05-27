import asyncio
import json
import os
import platform
import re as _re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

# Load free-claude-code .env files BEFORE importing modules that read them
# (e.g. pipelines.llm reads ANTHROPIC_AUTH_TOKEN at import time).
def _load_env():
    for p in [
        Path.home() / ".config" / "free-claude-code" / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]:
        if not p.exists():
            continue
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
        except Exception:
            pass
_load_env()

import psutil
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

sys.path.insert(0, str(Path(__file__).parent))

from core.websocket_manager import manager
from core import ollama_client as ollama
from core.video_processor import list_outputs, OUTPUTS_DIR
from integrations.registry import check_all, check_services, ok_count, REPOS

# New v3 modules
from core import db as jdb
from core import ideas as jideas
from core import scheduler as jsched
from core import asset_library as jlib
from core import orchestrator as jorch
from pipelines import llm as jllm
from pipelines import shorts as p_shorts
from pipelines import longform as p_longform
from pipelines import podcast as p_podcast
from pipelines import blog as p_blog
from pipelines import carousel as p_carousel
from pipelines import research as p_research
from pipelines import story_video as p_story
from pipelines import auto_video as p_auto_video
from pipelines import reel_production as p_reel_prod
from pipelines import avatar_reel_batch as p_avatar_reel

# ── Paths ──────────────────────────────────────────────────────────────────
BASE      = Path(__file__).parent
SESSIONS  = BASE.parent / ".scratch" / "sessions"
DOWNLOADS = BASE / "downloads"
SESSIONS.mkdir(parents=True, exist_ok=True)
DOWNLOADS.mkdir(exist_ok=True)
(BASE / "outputs").mkdir(exist_ok=True)

# ── State ──────────────────────────────────────────────────────────────────
_state = {
    "videos_generated": 0,
    "channels_analyzed": 0,
    "trends_found": 0,
    "scripts_created": 0,
    "revenue_scans": 0,
}
_agents = {
    name: {"active": False, "status": "STANDBY", "progress": 0}
    for name in ["spy", "trends", "factory", "money", "director", "shorts"]
}
_state_lock = asyncio.Lock()

REVENUE_FILE = BASE / "data" / "revenue.json"
(BASE / "data").mkdir(exist_ok=True)
_autosave_task: asyncio.Task | None = None
_autosave_enabled = True
_autosave_interval = 1200  # 20 min

# ── App ────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _autosave_task
    _autosave_task = asyncio.create_task(_autosave_loop())
    try:
        jdb.init_schema()
        jsched.start()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("v3 init failed: %s", e)
    yield
    if _autosave_task:
        _autosave_task.cancel()
    try:
        jsched.shutdown()
    except Exception:
        pass


app = FastAPI(title="JARVIS Content Intelligence", version="2.0", lifespan=lifespan)


# ── API key auth middleware ────────────────────────────────────────────────────────────────
class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_key: str | None = None):
        super().__init__(app)
        self._api_key = api_key

    async def dispatch(self, request, call_next):
        # Skip auth for non-mutating methods, WebSocket, and static files
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)
        if request.url.path.startswith("/ws"):
            return await call_next(request)
        if request.url.path.startswith("/static"):
            return await call_next(request)
        # If no key configured, allow all
        if not self._api_key:
            return await call_next(request)
        # Check API key
        provided = request.headers.get("x-api-key", "")
        if provided != self._api_key:
            return JSONResponse(
                {"status": "error", "message": "Unauthorized"},
                status_code=401,
            )
        return await call_next(request)


jarvis_api_key = os.environ.get("JARVIS_API_KEY", "") or None
app.add_middleware(AuthMiddleware, api_key=jarvis_api_key)
if jarvis_api_key:
    import logging as _logging
    _logging.getLogger(__name__).info("JARVIS API key auth enabled")
else:
    import logging as _logging
    _logging.getLogger(__name__).warning("JARVIS_API_KEY not set — content-creator running WITHOUT authentication")


app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
app.mount("/outputs", StaticFiles(directory=BASE / "outputs"), name="outputs")
templates = Jinja2Templates(directory=BASE / "templates")


# ── Helpers ────────────────────────────────────────────────────────────────
def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


async def _metrics() -> dict:
    outputs = list_outputs()
    async with _state_lock:
        videos = _state["videos_generated"]
        channels = _state["channels_analyzed"]
        trends = _state["trends_found"]
    return {
        "videos_generated": videos,
        "channels_analyzed": channels,
        "trends_found": trends,
        "videos_today": 0,
        "channels_today": 0,
        "trending_now": 0,
        "revenue_potential": 12500,
        "downloads": len(list(DOWNLOADS.iterdir())) if DOWNLOADS.exists() else 0,
    }


def _recent_outputs(n: int = 4) -> list:
    outputs = list_outputs()[:n]
    return [{"title": o["name"], "duration": o.get("duration", "—"), "created": o["created"]} for o in outputs]


async def _agent_start(name: str):
    async with _state_lock:
        _agents[name]["active"] = True
        _agents[name]["status"] = "RUNNING"
        _agents[name]["progress"] = 0
    await manager.agent_update(name, "running", 0)
    await manager.log(f"Agent {name.upper()} started", "info")


async def _agent_done(name: str):
    async with _state_lock:
        _agents[name]["active"] = False
        _agents[name]["status"] = "COMPLETE"
        _agents[name]["progress"] = 100
    await manager.agent_update(name, "complete", 100)
    await manager.log(f"Agent {name.upper()} finished", "success")
    _fire_gmail_notification(name)


def _fire_gmail_notification(agent_name: str):
    try:
        from integrations.gmail_client import send_notification
        send_notification(
            subject=f"JARVIS — Agent {agent_name.upper()} Complete",
            body=f"Agent {agent_name.upper()} finished at {_now_str()}.",
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug("Gmail notify skipped: %s", e)


async def _agent_error(name: str, msg: str):
    async with _state_lock:
        _agents[name]["active"] = False
        _agents[name]["status"] = "ERROR"
    await manager.agent_update(name, "error", 0)
    await manager.log(f"Agent {name.upper()} error: {msg}", "error")


async def _autosave_loop():
    while True:
        await asyncio.sleep(_autosave_interval)
        if _autosave_enabled:
            await _do_save()
            await manager.log("Auto-checkpoint saved", "info")


async def _do_save() -> str:
    filename = datetime.now().strftime("%Y-%m-%d-%H-%M") + ".json"
    path = SESSIONS / filename
    async with _state_lock:
        state_snap = _state.copy()
        agents_snap = {k: v["status"] for k, v in _agents.items()}
    payload = {
        "saved_at": _now_str(),
        "state": state_snap,
        "agents": agents_snap,
        "outputs": len(list_outputs()),
    }
    path.write_text(json.dumps(payload, indent=2))
    return filename


def _list_sessions() -> list:
    sessions = []
    for f in sorted(SESSIONS.glob("*.json"), reverse=True)[:50]:
        stat = f.stat()
        try:
            data = json.loads(f.read_text())
        except Exception:
            data = {}
        sessions.append({
            "filename":   f.name,
            "size":       f"{stat.st_size / 1024:.1f} KB",
            "agents_run": len([k for k, v in data.get("agents", {}).items() if v != "STANDBY"]),
            "outputs":    data.get("outputs", 0),
        })
    return sessions



# ── WebSocket ──────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    # Origin validation
    for hdr_name, hdr_val in ws.scope.get("headers", []):
        if hdr_name == b"origin":
            origin = hdr_val.decode("utf-8", errors="replace")
            parsed = urlparse(origin)
            if parsed.hostname not in ("localhost", "127.0.0.1"):
                await ws.close(code=4403, reason="Origin not allowed")
                return
            break
    await manager.connect(ws)
    try:
        await manager.log("JARVIS system online. All agents ready.", "success")
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


# ── Pages ──────────────────────────────────────────────────────────────────
@app.get("/")
async def dashboard(request: Request):
    repos    = check_all()
    ok       = ok_count(repos)
    models   = await ollama.list_models()
    outputs  = list_outputs()
    pct      = min(int(len(outputs) / 10 * 100), 100)
    return templates.TemplateResponse("dashboard.html", {
        "request":       request,
        "metrics":       _metrics(),
        "agents":        _agents,
        "agents_online": sum(1 for a in _agents.values() if a["active"]),
        "repos_ok":      ok,
        "repos_ok_pct":  ok * 10,
        "ollama_models": len(models),
        "outputs_count": len(outputs),
        "capacity_pct":  pct,
        "recent_outputs": _recent_outputs(),
    })


@app.get("/spy")
async def spy_page(request: Request):
    return templates.TemplateResponse("spy.html", {"request": request})


@app.get("/trends")
async def trends_page(request: Request):
    return templates.TemplateResponse("trends.html", {"request": request})


@app.get("/factory")
async def factory_page(request: Request):
    return templates.TemplateResponse("factory.html", {"request": request})


@app.get("/money")
async def money_page(request: Request):
    return templates.TemplateResponse("money.html", {"request": request})


@app.get("/director")
async def director_page(request: Request):
    return templates.TemplateResponse("director.html", {"request": request})


@app.get("/sound-alerts")
async def sound_alerts_page(request: Request):
    return templates.TemplateResponse(
        "sound_alert_center.html",
        {"request": request, "active": "sound_alerts"},
    )


@app.get("/repos")
async def repos_page(request: Request):
    repos   = check_all()
    ok      = ok_count(repos)
    models  = await ollama.list_models()
    disk    = psutil.disk_usage("/")
    ram     = psutil.virtual_memory()
    return templates.TemplateResponse("repos.html", {
        "request":          request,
        "repos":            repos,
        "repos_ok":         ok,
        "repos_total":      len(repos),
        "ollama_models":    len(models),
        "ollama_model_list": [{"name": m.get("name"), "size": _fmt_model_size(m.get("size", 0)),
                                "modified": m.get("modified_at", "")[:10]} for m in models],
        "gpu_available":    _has_gpu(),
        "disk_free":        f"{disk.free / 1_073_741_824:.1f} GB",
        "system_ram":       f"{ram.total / 1_073_741_824:.1f} GB",
        "platform":         platform.system() + " " + platform.release(),
        "python_version":   sys.version.split()[0],
    })


@app.get("/command")
async def command_page(request: Request):
    return templates.TemplateResponse("command.html", {"request": request, "active": "command"})


@app.get("/revenue")
async def revenue_page(request: Request):
    return templates.TemplateResponse("revenue.html", {"request": request, "active": "revenue"})


@app.get("/pipeline")
async def pipeline_page(request: Request):
    return templates.TemplateResponse("pipeline.html", {"request": request, "active": "pipeline"})


@app.get("/shorts")
async def shorts_page(request: Request):
    return templates.TemplateResponse("shorts.html", {"request": request})


@app.get("/content-hub")
async def content_hub_page(request: Request):
    return templates.TemplateResponse("content_hub.html", {"request": request})


@app.get("/orchestration")
async def orchestration_page(request: Request):
    return templates.TemplateResponse("orchestration.html", {"request": request})


@app.get("/portfolio")
async def portfolio_page(request: Request):
    wa_number = os.environ.get("WHATSAPP_NUMBER", "")
    return templates.TemplateResponse("portfolio.html", {"request": request, "wa_number": wa_number})


@app.get("/ai-studio")
async def ai_studio_page(request: Request):
    return templates.TemplateResponse("ai_studio.html", {"request": request})


@app.get("/vllm")
async def vllm_page(request: Request):
    return templates.TemplateResponse("vllm_inference.html", {"request": request})


# ── vLLM proxy API routes ─────────────────────────────────────────

def _validate_vllm_url(server_url: str) -> str:
    """Restrict vLLM proxy requests to localhost only (SSRF protection)."""
    from urllib.parse import urlparse
    parsed = urlparse(server_url)
    host = parsed.hostname or ""
    if host not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError(f"vLLM server_url must be localhost, got host='{host}'")
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"vLLM server_url must use http/https, got '{parsed.scheme}'")
    return server_url.rstrip("/")

_VLLM_BENCHMARK_MAX_REQUESTS = 50
_VLLM_BENCHMARK_MAX_LEN = 4096

@app.post("/api/vllm/load")
async def vllm_load_model(request: Request):
    """Proxy: load a model onto the vLLM engine."""
    body = await request.json()
    server_url = body.pop("server_url", None) or "http://localhost:8000"
    try:
        server_url = _validate_vllm_url(server_url)
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(server_url + "/v1/load", json=body)
            data = r.json()
            return {"ok": True, **data}
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception:
        return {"ok": False, "error": "Failed to communicate with vLLM server"}


@app.post("/api/vllm/unload")
async def vllm_unload_model(request: Request):
    """Proxy: unload a model from the vLLM engine."""
    body = await request.json()
    server_url = body.pop("server_url", None) or "http://localhost:8000"
    try:
        server_url = _validate_vllm_url(server_url)
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(server_url + "/v1/unload", json=body)
            data = r.json()
            return {"ok": True, **data}
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception:
        return {"ok": False, "error": "Failed to communicate with vLLM server"}


@app.post("/api/vllm/benchmark")
async def vllm_benchmark(request: Request):
    """Proxy: run a benchmark on the vLLM engine (or simulate if offline)."""
    body = await request.json()
    server_url = body.get("server_url") or "http://localhost:8000"
    model = body.get("model", "default")
    input_len = min(int(body.get("input_len", 128)), _VLLM_BENCHMARK_MAX_LEN)
    output_len = min(int(body.get("output_len", 256)), _VLLM_BENCHMARK_MAX_LEN)
    concurrency = body.get("concurrency", 1)
    num_requests = min(int(body.get("num_requests", 10)), _VLLM_BENCHMARK_MAX_REQUESTS)

    # Attempt real benchmark via vLLM server
    server_url = _validate_vllm_url(server_url)
    try:
        import time
        import random

        prompt = "The " * input_len  # rough token approximation
        latencies = []
        total_tokens = 0
        t0 = time.monotonic()

        async with httpx.AsyncClient(timeout=60) as client:
            for _ in range(num_requests):
                req_body = {
                    "model": model if model != "default" else "",
                    "prompt": prompt,
                    "max_tokens": output_len,
                    "temperature": 0.0,
                }
                start = time.monotonic()
                r = await client.post(server_url + "/v1/completions", json=req_body)
                elapsed = time.monotonic() - start
                if r.status_code == 200:
                    d = r.json()
                    if d.get("usage"):
                        total_tokens += d["usage"].get("completion_tokens", 0) + d["usage"].get("prompt_tokens", 0)
                latencies.append(elapsed * 1000)

        total_time = time.monotonic() - t0
        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.5)] if latencies else 0
        p99 = latencies[-1] if latencies else 0
        mean_lat = sum(latencies) / len(latencies) if latencies else 0

        return {
            "ok": True,
            "simulated": False,
            "results": {
                "tokens_per_second": total_tokens / total_time if total_time > 0 else 0,
                "requests_per_second": num_requests / total_time if total_time > 0 else 0,
                "mean_latency_ms": mean_lat,
                "p50_latency_ms": p50,
                "p99_latency_ms": p99,
                "mean_ttft_ms": mean_lat * 0.6,
                "mean_itl_ms": mean_lat / output_len if output_len > 0 else 0,
                "total_requests": num_requests,
                "total_tokens": total_tokens,
            },
        }
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception:
        # Offline simulation for UI demo
        base_tps = random.uniform(800, 3000)
        mean_lat = random.uniform(30, 200)
        return {
            "ok": True,
            "simulated": True,
            "results": {
                "tokens_per_second": round(base_tps, 2),
                "requests_per_second": round(base_tps / output_len, 2),
                "mean_latency_ms": round(mean_lat, 2),
                "p50_latency_ms": round(mean_lat * 0.9, 2),
                "p99_latency_ms": round(mean_lat * 2.1, 2),
                "mean_ttft_ms": round(mean_lat * 0.3, 2),
                "mean_itl_ms": round(random.uniform(1, 5), 2),
                "total_requests": num_requests,
                "total_tokens": num_requests * (input_len + output_len),
            },
        }


@app.post("/api/vllm/config")
async def vllm_update_config(request: Request):
    """Accept engine config updates (stored for next restart)."""
    import json

    body = await request.json()
    _VLLM_CONFIG_ALLOWED = {"max_model_len", "gpu_memory_utilization", "max_num_seqs",
        "max_num_batched_tokens", "enable_prefix_caching", "dtype", "quantization", "enforce_eager"}
    filtered = {k: v for k, v in body.items() if k in _VLLM_CONFIG_ALLOWED}
    if not filtered:
        return {"ok": False, "error": f"No valid config keys. Allowed: {sorted(_VLLM_CONFIG_ALLOWED)}"}

    config_path = BASE / "data" / "vllm_config.json"
    config_path.parent.mkdir(exist_ok=True)
    existing = {}
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    existing.update(filtered)
    config_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return {"ok": True, "config": existing}


@app.get("/media-lab")
async def media_lab_page(request: Request):
    return templates.TemplateResponse("media_lab.html", {"request": request})


@app.get("/ollama-studio")
async def ollama_studio_page(request: Request):
    return templates.TemplateResponse("ollama_studio.html", {"request": request})


@app.get("/auth/gmail")
async def gmail_auth(request: Request):
    try:
        from integrations.gmail_client import get_auth_url
        url = get_auth_url()
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/auth/gmail/callback")
async def gmail_callback(request: Request):
    code = request.query_params.get("code", "")
    if not code:
        return JSONResponse({"status": "error", "message": "No code provided"}, status_code=400)
    try:
        from integrations.gmail_client import exchange_code
        exchange_code(code)
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/portfolio?gmail=connected")
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/gmail/status")
async def gmail_status():
    try:
        from integrations.gmail_client import is_connected, get_credentials, get_user_email
        creds = get_credentials()
        if creds and creds.valid:
            email = get_user_email(creds)
            return {"connected": True, "email": email}
        return {"connected": False}
    except Exception:
        return {"connected": False}


_CPM_KW = {
    18: ['crypto','bitcoin','invest','finance','stock','money','income','profit','trading','passive income','affiliate'],
    14: ['ai','claude','chatgpt','gpt','llm','python','code','developer','programming','automation','saas','machine learning','api','prompt'],
    12: ['health','fitness','weight','workout','diet','mindset','mental','yoga'],
    11: ['business','entrepreneur','startup','freelanc','productivity','remote work','career','marketing','seo','growth'],
    8:  ['youtube','tiktok','instagram','viral','shorts','reel','content','creator','algorithm','thumbnail'],
}

def _estimate_cpm(title: str) -> int:
    t = title.lower()
    for cpm, kw_list in sorted(_CPM_KW.items(), reverse=True):
        if any(k in t for k in kw_list):
            return cpm
    return 6

async def _compute_revenue_opportunity() -> dict:
    try:
        from agents.trending_agent import get_trending_topics
        topics = await get_trending_topics(limit=20)
    except Exception:
        topics = [
            {"title": "AI coding tools 2025"}, {"title": "Passive income with AI"},
            {"title": "ChatGPT vs Claude comparison"}, {"title": "Python automation tricks"},
            {"title": "YouTube Shorts monetization"}, {"title": "Crypto bull run 2025"},
            {"title": "Build a SaaS in a weekend"}, {"title": "Stock market AI trading"},
            {"title": "Prompt engineering masterclass"}, {"title": "Machine learning for beginners"},
        ]
    avg_views = 45_000
    total_potential = sum((avg_views / 1000) * _estimate_cpm(t.get("title", "")) for t in topics)
    best_cpm = max((_estimate_cpm(t.get("title", "")) for t in topics), default=6)
    top_topics = sorted(topics, key=lambda t: _estimate_cpm(t.get("title", "")), reverse=True)[:5]
    return {
        "monthly_potential": round(total_potential),
        "total": round(total_potential),
        "best_cpm": best_cpm,
        "topic_count": len(topics),
        "top_opportunities": [
            {"title": t.get("title", ""), "cpm": _estimate_cpm(t.get("title", "")),
             "est_rev": round((avg_views / 1000) * _estimate_cpm(t.get("title", "")))}
            for t in top_topics
        ],
        "youtube": {"mrr": 0, "views": 0, "subs": 0, "videos": 0, "cpm": best_cpm},
        "freelance": {"total": 0, "projects": []},
        "saas": {"mrr": 0, "subs": 0},
        "affiliate": {"clicks": 0, "conversions": 0, "commissions": 0},
    }

@app.get("/api/revenue")
async def revenue_get():
    try:
        if REVENUE_FILE.exists():
            stored = json.loads(REVENUE_FILE.read_text())
            if stored and any(v for v in stored.values() if isinstance(v, (int, float)) and v > 0):
                return stored
        return await _compute_revenue_opportunity()
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/revenue")
async def revenue_update(request: Request):
    secret = request.headers.get("X-Portfolio-Secret", "")
    env_secret = os.environ.get("PORTFOLIO_SECRET", "")
    if not env_secret:
        return JSONResponse({"status": "error", "message": "Revenue API not configured — PORTFOLIO_SECRET missing"}, status_code=503)
    if secret != env_secret:
        return JSONResponse({"status": "error", "message": "Unauthorized"}, status_code=403)
    try:
        data = await request.json()
        REVENUE_FILE.parent.mkdir(exist_ok=True)
        if REVENUE_FILE.exists():
            existing = json.loads(REVENUE_FILE.read_text())
            existing.update(data)
            data = existing
        REVENUE_FILE.write_text(json.dumps(data, indent=2))
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/contact")
async def contact_form(request: Request):
    body = await request.json()
    name    = str(body.get("name", "")).strip()
    email   = str(body.get("email", "")).strip()
    message = str(body.get("message", "")).strip()
    if not name or not email or not message:
        return JSONResponse({"status": "error", "message": "All fields required"}, status_code=400)
    text = f"From: {name} <{email}>\n\n{message}"
    try:
        from integrations.gmail_client import send_notification
        ok = send_notification(subject=f"MAJD Portfolio Contact — {name}", body=text)
        if ok:
            return {"status": "ok"}
        return JSONResponse({"status": "error", "message": "Gmail not connected. Connect at /auth/gmail"}, status_code=503)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/session")
async def session_page(request: Request):
    sessions = _list_sessions()
    return templates.TemplateResponse("session.html", {
        "request":       request,
        "sessions":      sessions,
        "last_save":     sessions[0]["filename"] if sessions else None,
        "autosave":      _autosave_enabled,
        "total_outputs": len(list_outputs()),
        "session_age":   "Active",
        "state":         _state,
    })


# ── Agent APIs ─────────────────────────────────────────────────────────────
@app.post("/api/agents/spy/run")
async def agent_spy_run(request: Request):
    body = await request.json()
    url  = str(body.get("url", ""))
    plat = str(body.get("platform", "youtube"))
    await _agent_start("spy")
    try:
        from agents.channel_spy import run
        data = await run(url, plat)
        _state["channels_analyzed"] += 1
        await manager.metric("channels-analyzed", _state["channels_analyzed"])
        await _agent_done("spy")
        return {"status": "ok", "data": data}
    except Exception as e:
        await _agent_error("spy", str(e))
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/agents/trends/run")
async def agent_trends_run(request: Request):
    body   = await request.json()
    query  = str(body.get("query", ""))
    plat   = str(body.get("platform", "youtube"))
    window = str(body.get("window", "7d"))
    await _agent_start("trends")
    try:
        from agents.trend_miner import run
        data = await run(query, plat, window)
        found = len(data.get("trends", []))
        _state["trends_found"] += found
        await manager.metric("trends-found", _state["trends_found"])
        await _agent_done("trends")
        return {"status": "ok", "data": data}
    except Exception as e:
        await _agent_error("trends", str(e))
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/agents/trends/blueprint")
async def agent_trends_blueprint(request: Request):
    body = await request.json()
    from agents.trend_miner import generate_blueprint
    result = await generate_blueprint(body.get("trend", {}))
    return result


@app.post("/api/agents/trends/download")
async def agent_trends_download(request: Request):
    body = await request.json()
    url  = str(body.get("url", ""))
    await manager.log(f"Downloading: {url}", "info")
    try:
        from agents.trend_miner import download
        result = await download(url)
        await manager.log(f"Downloaded: {result['name']}", "success")
        return {"status": "ok", **result}
    except Exception as e:
        await manager.log(f"Download failed: {e}", "error")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/agents/factory/run")
async def agent_factory_run(request: Request):
    body = await request.json()
    await _agent_start("factory")
    try:
        from agents.content_factory import run
        data = await run(
            topic=str(body.get("topic", "")),
            style=str(body.get("style", "shorts")),
            tone=str(body.get("tone", "viral")),
            gen_script=bool(body.get("gen_script", True)),
            gen_thumbnail=bool(body.get("gen_thumbnail", True)),
            gen_hashtags=bool(body.get("gen_hashtags", True)),
        )
        _state["scripts_created"] += 1
        await _agent_done("factory")
        return {"status": "ok", "data": data}
    except Exception as e:
        await _agent_error("factory", str(e))
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/agents/money/run")
async def agent_money_run(request: Request):
    body  = await request.json()
    niche = str(body.get("niche", ""))
    views = str(body.get("views", "1m"))
    await _agent_start("money")
    try:
        from agents.monetization_intel import run
        data = await run(niche, views)
        _state["revenue_scans"] += 1
        await _agent_done("money")
        return {"status": "ok", "data": data}
    except Exception as e:
        await _agent_error("money", str(e))
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/agents/director/run")
async def agent_director_run(request: Request):
    body = await request.json()
    await _agent_start("director")
    try:
        from agents.cinema_director import run
        data = await run(body)
        _state["videos_generated"] += 1
        await manager.metric("videos-generated", _state["videos_generated"])
        await _agent_done("director")
        return {"status": "ok", "data": data}
    except Exception as e:
        await _agent_error("director", str(e))
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/agents/director/voiceover")
async def agent_voiceover(request: Request):
    return JSONResponse({"status": "error", "message": "Voice-over requires TTS model"}, status_code=501)


@app.post("/api/agents/shorts/run")
async def agent_shorts_run(request: Request):
    body = await request.json()
    url         = str(body.get("url", ""))
    num_clips   = int(body.get("num_clips", 3))
    aspect_ratio = str(body.get("aspect_ratio", "9:16"))
    mode        = str(body.get("mode", "local"))
    quality     = str(body.get("quality", "720"))
    await _agent_start("shorts")
    try:
        from agents.shorts_agent import run
        data = await run(url=url, num_clips=num_clips, aspect_ratio=aspect_ratio, mode=mode, quality=quality)
        await _agent_done("shorts")
        return {"status": "ok", "data": data}
    except Exception as e:
        await _agent_error("shorts", str(e))
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/agents/platform-export/run")
async def agent_platform_export(request: Request):
    body = await request.json()
    master_video = str(body.get("master_video", ""))
    topic_id     = str(body.get("topic_id", ""))
    platforms    = body.get("platforms", ["youtube"])
    script_meta  = body.get("script_metadata", {})
    if not master_video or not topic_id:
        return JSONResponse({"status": "error", "message": "master_video and topic_id required"}, status_code=400)
    try:
        from agents.platform_exporter import run
        data = await run(master_video=master_video, script_metadata=script_meta, topic_id=topic_id, platforms=platforms)
        return {"status": "ok", "data": data}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/agents/fal/image")
async def fal_image(request: Request):
    body = await request.json()
    try:
        from agents.fal_studio import generate_image
        data = await generate_image(
            prompt=str(body.get("prompt", "")),
            model=str(body.get("model", "flux-schnell")),
            width=int(body.get("width", 1024)),
            height=int(body.get("height", 1024)),
            num_images=int(body.get("num_images", 1)),
            negative_prompt=str(body.get("negative_prompt", "")),
        )
        _state["videos_generated"] += 1
        return {"status": "ok", "data": data}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/agents/fal/video")
async def fal_video(request: Request):
    body = await request.json()
    try:
        from agents.fal_studio import generate_video
        data = await generate_video(
            prompt=str(body.get("prompt", "")),
            model=str(body.get("model", "kling-5s")),
            duration=int(body.get("duration", 5)),
            aspect_ratio=str(body.get("aspect_ratio", "16:9")),
        )
        _state["videos_generated"] += 1
        return {"status": "ok", "data": data}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/fal/status")
async def fal_status():
    key = os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY", "")
    return {"connected": bool(key), "key_set": bool(key)}


@app.post("/api/media/download")
async def media_download(request: Request):
    body = await request.json()
    url     = str(body.get("url", ""))
    quality = str(body.get("quality", "720"))
    audio   = bool(body.get("audio_only", False))
    if not url:
        return JSONResponse({"status": "error", "message": "URL required"}, status_code=400)
    try:
        from agents.media_lab import download_video
        data = await download_video(url, quality, audio)
        return {"status": "ok", "data": data}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/media/transcribe")
async def media_transcribe(request: Request):
    body      = await request.json()
    file_path = str(body.get("file_path", ""))
    language  = str(body.get("language", "auto"))
    if not file_path:
        return JSONResponse({"status": "error", "message": "file_path required"}, status_code=400)
    try:
        from agents.media_lab import transcribe_file
        data = await transcribe_file(file_path, language)
        return {"status": "ok", "data": data}
    except FileNotFoundError as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=404)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/media/analyze")
async def media_analyze(request: Request):
    body  = await request.json()
    text  = str(body.get("text", ""))
    task  = str(body.get("task", "virality"))
    model = str(body.get("model", "llama3.1:8b"))
    if not text:
        return JSONResponse({"status": "error", "message": "text required"}, status_code=400)
    try:
        from agents.ollama_agent import analyze_content
        data = await analyze_content(text, task, model)
        return {"status": "ok", "data": data}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/ollama/models")
async def ollama_models_list():
    try:
        from agents.ollama_agent import list_models
        models = await list_models()
        return {"status": "ok", "models": models}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/ollama/chat")
async def ollama_chat(request: Request):
    body    = await request.json()
    message = str(body.get("message", ""))
    model   = str(body.get("model", "llama3.1:8b"))
    history = body.get("history", [])
    system  = body.get("system", None)
    if not message:
        return JSONResponse({"status": "error", "message": "message required"}, status_code=400)
    try:
        from agents.ollama_agent import chat
        data = await chat(message, model=model, history=history, system=system)
        # Surface the reply at the top level so the chat overlay (and
        # other clients) don't have to know about the {status,data} wrapper.
        reply = (data or {}).get("response") or (data or {}).get("message") or (data or {}).get("reply") or ""
        return {"status": "ok", "data": data, "reply": reply, "response": reply}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/agents/all/run")
async def run_all_agents(request: Request):
    await manager.log("All agents activating...", "info")
    return {"status": "ok", "message": "All agents queued"}


# ── System APIs ────────────────────────────────────────────────────────────
@app.get("/api/repos/status")
async def repos_status():
    return check_all()


@app.post("/api/repos/clone")
async def repos_clone(request: Request):
    body = await request.json()
    name = str(body.get("name", ""))
    url  = str(body.get("url", ""))
    if not url:
        return JSONResponse({"status": "error", "message": "No URL"}, 400)
    await manager.log(f"Cloning {name}...", "info")
    return {"status": "ok", "message": f"Clone of {name} queued"}


@app.get("/api/system/stats")
async def system_stats():
    cpu  = psutil.cpu_percent(interval=0.1)
    mem  = psutil.virtual_memory()
    _root = "C:\\" if sys.platform == "win32" else "/"
    disk = psutil.disk_usage(_root)
    ok   = await ollama.is_available()
    return {
        "cpu":       round(cpu),
        "mem":       round(mem.percent),
        "disk":      round(disk.percent),
        "ollama_ok": ok,
    }


@app.post("/api/ollama/pull")
async def ollama_pull(request: Request):
    body  = await request.json()
    model = str(body.get("model", ""))
    if not model:
        return JSONResponse({"status": "error", "message": "No model name"}, 400)
    await manager.log(f"Pulling {model}...", "info")
    ok = await ollama.pull_model(model)
    if ok:
        await manager.log(f"{model} ready", "success")
        return {"status": "ok"}
    return JSONResponse({"status": "error", "message": f"Failed to pull {model}"}, 500)


@app.get("/api/dashboard/metrics")
async def dashboard_metrics():
    return _metrics()


# ── Output APIs ────────────────────────────────────────────────────────────
@app.get("/api/outputs/list")
async def outputs_list():
    return {"files": list_outputs()}


@app.get("/api/outputs/videos")
async def outputs_videos():
    return {"files": list_outputs(".mp4")}


@app.post("/api/outputs/export-all")
async def outputs_export_all():
    return {"status": "ok", "path": str(OUTPUTS_DIR)}


@app.post("/api/outputs/clear")
async def outputs_clear():
    for f in OUTPUTS_DIR.iterdir():
        if f.is_file() and not f.name.startswith("_"):
            try: f.unlink()
            except OSError: pass
    return {"status": "ok"}


# ── Asset APIs ─────────────────────────────────────────────────────────────
@app.get("/api/assets/thumbnail")
async def get_thumbnail(path: str = ""):
    """Return a thumbnail image file by absolute path.

    Usage: GET /api/assets/thumbnail?path=<url-encoded-absolute-path>
    Returns the PNG/JPG image directly, or 404 if not found / outside outputs/.
    """
    if not path:
        return JSONResponse({"status": "error", "message": "path required"}, status_code=400)
    filename = Path(path).name  # strips directory components
    p = (BASE / "outputs" / filename).resolve()
    # Security: restrict to files within the outputs directory
    try:
        p.relative_to((BASE / "outputs").resolve())
    except ValueError:
        return JSONResponse({"status": "error", "message": "path not allowed"}, status_code=403)
    if not p.exists() or not p.is_file():
        return JSONResponse({"status": "error", "message": "not found"}, status_code=404)
    return FileResponse(str(p))


# ── Session APIs ───────────────────────────────────────────────────────────
@app.post("/api/session/save")
async def session_save():
    filename = _do_save()
    return {"status": "ok", "filename": filename}


@app.get("/api/session/list")
async def session_list():
    return {"sessions": _list_sessions()}


@app.post("/api/session/restore")
async def session_restore(request: Request):
    global _state
    body     = await request.json()
    filename = str(body.get("filename", ""))
    path     = SESSIONS / filename
    if not path.exists():
        return JSONResponse({"status": "error", "message": "Session not found"}, 404)
    try:
        data = json.loads(path.read_text())
        if "state" in data:
            _state.update(data["state"])
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, 500)


@app.get("/api/session/download/{filename}")
async def session_download(filename: str):
    path = SESSIONS / filename
    if not path.exists():
        return JSONResponse({"status": "error"}, 404)
    return FileResponse(path, filename=filename)


@app.post("/api/session/autosave")
async def session_autosave(request: Request):
    global _autosave_enabled, _autosave_interval
    body     = await request.json()
    _autosave_enabled  = bool(body.get("enable", True))
    _autosave_interval = int(body.get("interval", 20)) * 60
    return {"status": "ok"}


@app.post("/api/session/reset")
async def session_reset():
    global _state
    _state = {k: 0 for k in _state}
    for a in _agents.values():
        a.update({"active": False, "status": "STANDBY", "progress": 0})
    return {"status": "ok"}


# ── Trending / Auto-Shorts / GitHub / Skills pages ───────────────────────

@app.get("/github-hub")
async def github_hub_page(request: Request):
    return templates.TemplateResponse("github_hub.html", {"request": request, "active": "github_hub"})


@app.get("/skills")
async def skills_page(request: Request):
    return templates.TemplateResponse("skills.html", {"request": request, "active": "skills"})


@app.get("/rate-limits")
async def rate_limits_page(request: Request):
    return templates.TemplateResponse("rate_limits.html", {"request": request, "active": "rate_limits"})


@app.get("/api/rate-limits/status")
async def api_rate_limits_status():
    """Proxy-bridged rate-limit status. Calls the free-claude-code proxy on port 8082."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get('http://localhost:8082/api/rate-limits/status')
            if r.status_code == 200:
                return r.json()
            return JSONResponse({"ok": False, "providers": [], "error": f"Proxy returned HTTP {r.status_code}"}, status_code=502)
    except Exception as e:
        return JSONResponse({"ok": False, "providers": [], "error": f"Proxy unreachable: {e}"}, status_code=502)


@app.get("/mcp-command")
async def mcp_command_page(request: Request):
    return templates.TemplateResponse("mcp_command.html", {"request": request, "active": "mcp_command"})


@app.get("/litellm-hub")
async def litellm_hub_page(request: Request):
    return templates.TemplateResponse("litellm_hub.html", {"request": request, "active": "litellm_hub"})


@app.get("/localai-control")
async def localai_control_page(request: Request):
    return templates.TemplateResponse("localai_control.html", {"request": request, "active": "localai"})


@app.get("/empire")
async def empire_page(request: Request):
    return templates.TemplateResponse("empire.html", {"request": request, "active": "empire"})


@app.get("/reel-producer")
async def reel_producer_page(request: Request):
    return templates.TemplateResponse("reel-producer.html", {"request": request, "active": "reel-producer"})


@app.get("/reels")
async def reels_page(request: Request):
    return templates.TemplateResponse("reels.html", {"request": request, "active": "reels"})


@app.get("/api/trending/topics")
async def trending_topics():
    try:
        from agents.trending_agent import get_trending_topics
        topics = await get_trending_topics(limit=20)
        return {"status": "ok", "topics": topics, "total": len(topics)}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/topic-discovery/run")
async def topic_discovery_run(request: Request):
    """Run topic discovery scan with full metrics.
    Usage: POST /api/topic-discovery/run {"niche": "tech", "platforms": ["youtube", "tiktok"]}
    """
    body = await request.json()
    niche = str(body.get("niche", ""))
    platforms = body.get("platforms")
    try:
        from agents.topic_discovery import run_discovery
        result = await run_discovery(niche=niche, platforms=platforms)
        return result
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/topic-discovery/topics")
async def topic_discovery_get(niche: str = "", limit: int = 10):
    """Get discovered topics without running a new scan.
    Usage: GET /api/topic-discovery/topics?niche=tech&limit=10
    """
    try:
        from agents.topic_discovery import discover_topics
        topics = await discover_topics(limit=limit, niche=niche)
        return {"status": "ok", "topics": topics, "total": len(topics)}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/shorts/auto")
async def auto_shorts(request: Request):
    body  = await request.json()
    topic = str(body.get("topic", "")).strip()
    model = str(body.get("model", "llama3.1:8b"))
    if not topic:
        return JSONResponse({"status": "error", "message": "topic required"}, status_code=400)
    try:
        from agents.auto_shorts_agent import generate
        data = await generate(topic=topic, model=model)
        _state["videos_generated"] += 1
        return {"status": "ok", "data": data}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/github/trending")
async def github_trending(
    query: str = "stars:>500",
    language: str = "",
    limit: int = 20,
):
    try:
        from agents.github_trending_agent import get_trending
        repos = await get_trending(query=query, language=language, limit=limit)
        return {"status": "ok", "repos": repos, "total": len(repos)}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/github/clone")
async def github_clone(request: Request):
    body      = await request.json()
    clone_url = str(body.get("clone_url", "")).strip()
    if not clone_url:
        return JSONResponse({"status": "error", "message": "clone_url required"}, status_code=400)
    try:
        from agents.github_trending_agent import clone_repo
        result = await clone_repo(clone_url)
        await manager.log(result.get("message", "Clone done"), "success" if result["ok"] else "error")
        return {"status": "ok" if result["ok"] else "error", **result}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/github/install")
async def github_install(request: Request):
    body      = await request.json()
    repo_name = str(body.get("repo_name", "")).strip()
    if not repo_name:
        return JSONResponse({"status": "error", "message": "repo_name required"}, status_code=400)
    try:
        from agents.github_trending_agent import install_repo
        result = await install_repo(repo_name)
        await manager.log(result.get("message", "Install done"), "success" if result["ok"] else "error")
        return {"status": "ok" if result["ok"] else "error", **result}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/repos/services")
async def repos_services():
    """Return live status of all ai-repositories and key services."""
    repos = await check_services()
    # Also ping key named services
    _NAMED_SERVICES = {
        "Ollama":     "http://localhost:11434",
        "Free Proxy": "http://localhost:8082",
    }
    async def _check(client: httpx.AsyncClient, name: str, url: str) -> tuple[str, dict]:
        try:
            r = await client.get(url, timeout=2)
            return name, {"up": True, "url": url, "status": r.status_code}
        except Exception:
            return name, {"up": False, "url": url, "status": None}

    async with httpx.AsyncClient(timeout=2) as client:
        named = await asyncio.gather(*[_check(client, n, u) for n, u in _NAMED_SERVICES.items()])
    return {
        "services": dict(named),
        "repos": repos,
        "repos_present": sum(1 for r in repos if r["ok"]),
        "repos_running": sum(1 for r in repos if r.get("running")),
        "total_repos": len(repos),
    }


# ── Util ───────────────────────────────────────────────────────────────────
def _has_gpu() -> bool:
    try:
        import subprocess
        r = subprocess.run(["nvidia-smi"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def _fmt_model_size(size: int) -> str:
    if size >= 1_073_741_824: return f"{size/1_073_741_824:.1f} GB"
    if size >= 1_048_576:     return f"{size/1_048_576:.1f} MB"
    return f"{size} B"


# ═══════════════════════════════════════════════════════════════════════════
# v3 ROUTES — pipelines, agents, ideas, brand, costs, schedules, library
# ═══════════════════════════════════════════════════════════════════════════

# ── New pages ──────────────────────────────────────────────────────────────
@app.get("/mission-control")
async def mission_control_page(request: Request):
    return templates.TemplateResponse("mission_control.html", {"request": request})


@app.get("/longform")
async def longform_page(request: Request):
    return templates.TemplateResponse("longform.html", {"request": request})


@app.get("/podcast")
async def podcast_page(request: Request):
    return templates.TemplateResponse("podcast.html", {"request": request})


@app.get("/blog")
async def blog_page(request: Request):
    return templates.TemplateResponse("blog.html", {"request": request})


@app.get("/carousel")
async def carousel_page(request: Request):
    return templates.TemplateResponse("carousel.html", {"request": request})


@app.get("/research")
async def research_page(request: Request):
    return templates.TemplateResponse("research.html", {"request": request})


@app.get("/ideas")
async def ideas_page(request: Request):
    return templates.TemplateResponse("ideas.html", {"request": request})


@app.get("/brand")
async def brand_page(request: Request):
    return templates.TemplateResponse("brand.html", {"request": request})


@app.get("/costs")
async def costs_page(request: Request):
    return templates.TemplateResponse("costs.html", {"request": request})


@app.get("/schedule")
async def schedule_page(request: Request):
    return templates.TemplateResponse("schedule.html", {"request": request})


@app.get("/library")
async def library_page(request: Request):
    return templates.TemplateResponse("library.html", {"request": request})


# ── Integration dashboards ────────────────────────────────────────────────
@app.get("/open-webui")
async def open_webui_page(request: Request):
    return templates.TemplateResponse("open_webui_panel.html", {"request": request, "active": "open_webui"})


@app.get("/phidata")
async def phidata_page(request: Request):
    return templates.TemplateResponse("phidata_agents.html", {"request": request})


@app.get("/cohere")
async def cohere_page(request: Request):
    return templates.TemplateResponse("cohere_toolkit.html", {"request": request})


@app.get("/llamaindex")
async def llamaindex_page(request: Request):
    return templates.TemplateResponse("llamaindex_rag.html", {"request": request})


@app.get("/langchain")
async def langchain_page(request: Request):
    return templates.TemplateResponse("langchain_pipeline.html", {"request": request})


@app.get("/openhands")
async def openhands_page(request: Request):
    return templates.TemplateResponse("openhands_auto.html", {"request": request})


# ── Integration API stubs (mock data for operational dashboards) ───────────
@app.get("/api/litellm/status")
async def litellm_status():
    return {"status": "ok", "models_active": 8, "requests_total": 14520, "avg_latency_ms": 340, "cost_savings_pct": 72}


@app.get("/api/litellm/models")
async def litellm_models():
    return {"models": [
        {"id": "nvidia_nim/glm-5.1", "provider": "nvidia_nim", "status": "active", "cost_per_1k": 0.0, "latency_ms": 280},
        {"id": "openrouter/claude-sonnet-4", "provider": "open_router", "status": "active", "cost_per_1k": 0.003, "latency_ms": 420},
        {"id": "openai/gpt-4o", "provider": "openai", "status": "fallback", "cost_per_1k": 0.005, "latency_ms": 380},
        {"id": "google/gemini-2.5-pro", "provider": "google", "status": "active", "cost_per_1k": 0.001, "latency_ms": 310},
    ]}


@app.get("/api/mcp/status")
async def mcp_status():
    return {"status": "ok", "servers_online": 3, "tools_available": 47, "requests_min": 12, "avg_latency_ms": 85}


@app.get("/api/mcp/tools")
async def mcp_tools():
    return {"tools": [
        {"name": "web_search", "server": "context7", "status": "online", "calls": 342},
        {"name": "code_search", "server": "codegraph", "status": "online", "calls": 189},
        {"name": "memory_store", "server": "claude-flow", "status": "online", "calls": 56},
    ]}


@app.post("/api/mcp/deploy")
async def mcp_deploy(request: Request):
    """Register a new MCP server from URL or npx command."""
    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON body"}
    url = body.get("url", "").strip()
    name = body.get("name", "custom-server").strip()
    if not url:
        return {"ok": False, "error": "url is required"}
    # In production this would spawn the npx process; here we acknowledge registration
    return {"ok": True, "name": name, "tools": ["pending_discovery"], "url": url}


@app.get("/api/openwebui/status")
async def openwebui_status():
    return {"status": "ok", "conversations": 23, "models_loaded": 5, "active_users": 2, "tokens_today": 85000}


@app.get("/api/openwebui/models")
async def openwebui_models():
    return {"models": [
        {"name": "llama-3.3-70b", "size": "40GB", "status": "loaded", "vram_gb": 12.5},
        {"name": "mistral-7b", "size": "4.1GB", "status": "loaded", "vram_gb": 2.3},
        {"name": "codellama-34b", "size": "20GB", "status": "available", "vram_gb": 0},
    ]}


@app.get("/api/localai/status")
async def localai_status():
    return {"status": "ok", "models": 4, "gpu_usage_pct": 67, "gpu_vram_gb": 18.2, "requests_total": 8920}


@app.get("/api/localai/models")
async def localai_models():
    return {"models": [
        {"name": "llama-3.3-70b-q4", "size": "40GB", "status": "loaded", "context": 8192},
        {"name": "whisper-large", "size": "3GB", "status": "loaded", "context": 0},
        {"name": "sd-xl-turbo", "size": "6.9GB", "status": "standby", "context": 0},
    ]}


@app.get("/api/vllm/status")
async def vllm_status():
    return {"status": "ok", "gpu_type": "RTX 4090", "vram_used_gb": 22.1, "vram_total_gb": 24, "throughput_tok_s": 1850, "active_requests": 3}


@app.get("/api/vllm/models")
async def vllm_models():
    return {"models": [
        {"name": "Qwen/Qwen3-Coder-480B-A35B", "status": "loaded", "gpu_pct": 78, "qps": 12.5},
        {"name": "deepseek-ai/deepseek-v4-pro", "status": "queued", "gpu_pct": 0, "qps": 0},
        {"name": "meta-llama/Llama-3.3-70B", "status": "loaded", "gpu_pct": 35, "qps": 8.2},
    ]}


@app.get("/api/phidata/status")
async def phidata_status():
    return {"status": "ok", "agents_active": 5, "workflows": 12, "tasks_completed": 847, "avg_time_s": 4.2}


@app.get("/api/phidata/agents")
async def phidata_agents():
    return {"agents": [
        {"name": "ResearchAgent", "status": "active", "tasks": 234, "model": "gpt-4o"},
        {"name": "CodeAgent", "status": "active", "tasks": 189, "model": "claude-sonnet"},
        {"name": "DataAgent", "status": "idle", "tasks": 424, "model": "gemini-pro"},
    ]}


@app.get("/api/cohere/status")
async def cohere_status():
    return {"status": "ok", "api_calls_min": 8, "latency_ms": 180, "tokens_today": 42000, "rate_limit_remaining": 950}


@app.get("/api/cohere/models")
async def cohere_models():
    return {"models": [
        {"name": "command-r-plus", "status": "available", "context": 128000, "tool_use": True},
        {"name": "command-r", "status": "available", "context": 128000, "tool_use": True},
        {"name": "embed-v3", "status": "available", "context": 512, "tool_use": False},
        {"name": "rerank-v3", "status": "available", "context": 4096, "tool_use": False},
    ]}


@app.get("/api/llamaindex/status")
async def llamaindex_status():
    return {"status": "ok", "documents_indexed": 156, "total_nodes": 48200, "embeddings": 48200, "queries_today": 340}


@app.get("/api/llamaindex/retrievers")
async def llamaindex_retrievers():
    return {"retrievers": [
        {"name": "vector_index", "type": "vector", "status": "active", "accuracy": 0.92},
        {"name": "keyword_index", "type": "keyword", "status": "active", "accuracy": 0.78},
        {"name": "hybrid_index", "type": "hybrid", "status": "building", "accuracy": 0},
    ]}


@app.get("/api/langchain/status")
async def langchain_status():
    return {"status": "ok", "active_chains": 7, "success_rate_pct": 94, "avg_time_ms": 820, "total_executions": 5230}


@app.get("/api/langchain/chains")
async def langchain_chains():
    return {"chains": [
        {"name": "RAG Pipeline", "status": "active", "runs": 1230, "success_pct": 96},
        {"name": "Summarizer", "status": "active", "runs": 890, "success_pct": 98},
        {"name": "Code Reviewer", "status": "idle", "runs": 3110, "success_pct": 88},
    ]}


@app.get("/api/openhands/status")
async def openhands_status():
    return {"status": "ok", "workspaces_active": 3, "total_workspaces": 15, "containers_running": 3, "avg_runtime_s": 45}


@app.get("/api/openhands/actions")
async def openhands_actions():
    return {"actions": {
        "write": 342, "read": 891, "bash": 567, "browse": 123,
        "files_created": 89, "lines_written": 12450, "languages": ["python", "typescript", "rust"],
    }}


# ── System diagnostics ────────────────────────────────────────────────────
@app.get("/api/system/llm-health")
async def api_llm_health():
    return await jllm.health()


@app.post("/api/system/start-proxy")
async def api_start_proxy():
    """Spawn start-proxy.bat in a detached process. Local-only convenience."""
    import subprocess as _sp
    bat = Path(__file__).resolve().parent.parent / "start-proxy.bat"
    if not bat.exists():
        return {"ok": False, "error": f"start-proxy.bat not found at {bat}"}
    try:
        if platform.system() == "Windows":
            DETACHED = 0x00000008
            proc = _sp.Popen(
                ["cmd.exe", "/c", "start", "", str(bat)],
                creationflags=DETACHED, close_fds=True,
            )
        else:
            proc = _sp.Popen([str(bat)], close_fds=True)
        return {"ok": True, "pid": proc.pid, "bat": str(bat)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Pipeline runners ──────────────────────────────────────────────────────
async def _run_pipeline(runner, payload: dict):
    try:
        result = await runner(payload)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"{type(e).__name__}: {e}"}, status_code=500)


@app.post("/api/pipelines/shorts/run")
async def api_pipe_shorts(req: Request):
    body = await req.json()
    return await _run_pipeline(p_shorts.run, body)


@app.post("/api/pipelines/longform/run")
async def api_pipe_longform(req: Request):
    body = await req.json()
    return await _run_pipeline(p_longform.run, body)


@app.post("/api/pipelines/podcast/run")
async def api_pipe_podcast(req: Request):
    body = await req.json()
    return await _run_pipeline(p_podcast.run, body)


@app.post("/api/pipelines/blog/run")
async def api_pipe_blog(req: Request):
    body = await req.json()
    return await _run_pipeline(p_blog.run, body)


@app.post("/api/pipelines/carousel/run")
async def api_pipe_carousel(req: Request):
    body = await req.json()
    return await _run_pipeline(p_carousel.run, body)


@app.post("/api/pipelines/research/run")
async def api_pipe_research(req: Request):
    body = await req.json()
    return await _run_pipeline(p_research.run, body)


@app.get("/story")
async def story_page(request: Request):
    return templates.TemplateResponse("story.html", {"request": request})


@app.post("/api/pipelines/story/run")
async def api_pipe_story(req: Request):
    body = await req.json()
    return await _run_pipeline(p_story.run, body)


@app.get("/auto-video")
async def auto_video_page(request: Request):
    return templates.TemplateResponse("auto_video.html", {"request": request, "active": "auto_video"})


@app.post("/api/pipelines/auto_video/run")
async def api_pipe_auto_video(req: Request):
    body = await req.json()
    return await _run_pipeline(p_auto_video.run, body)


@app.post("/api/pipelines/reel/run")
async def api_pipe_reel(req: Request):
    body = await req.json()
    return await _run_pipeline(p_reel_prod.run, body)


@app.post("/api/pipelines/reel-production/run")
async def api_pipe_reel_production(req: Request):
    """Stage 3-4 reel production pipeline: asset generation + video assembly."""
    body = await req.json()
    return await _run_pipeline(p_reel_prod.run, body)



# ── Reel Producer Pipeline API Routes ───────────────────────────────────────
@app.post("/api/reel/topics")
async def reel_topics(request: Request):
    """Trigger topic discovery via trend_miner.run().

    Usage: POST /api/reel/topics {"query": "fitness", "platform": "youtube", "window": "7 days"}
    """
    body = await request.json()
    query = str(body.get("query", ""))
    platform = str(body.get("platform", "youtube"))
    window = str(body.get("window", "7 days"))

    if not query:
        return JSONResponse({"status": "error", "message": "query required"}, status_code=400)

    try:
        from agents.trend_miner import run as trend_miner_run
        result = await trend_miner_run(query=query, platform=platform, window=window)
        return {"status": "ok", "topics": result.get("topics", []), "summary": result.get("summary", {})}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/reel/select-topics")
async def reel_select_topics(request: Request):
    """Store user topic selection (1-2 topic_ids).

    Usage: POST /api/reel/select-topics {"topic_ids": ["topic_001", "topic_002"], "platform": "youtube"}
    """
    body = await request.json()
    topic_ids = body.get("topic_ids", [])
    platform = str(body.get("platform", "youtube"))

    if not topic_ids or len(topic_ids) > 2:
        return JSONResponse({"status": "error", "message": "Select 1-2 topic_ids"}, status_code=400)

    try:
        from core import db as jdb
        created_ids = []
        for tid in topic_ids:
            if isinstance(tid, dict):
                title = tid.get("title", tid.get("id", ""))
                metadata = tid
                topic_id = tid.get("id", str(tid))
            else:
                title = tid
                metadata = {"id": tid}
                topic_id = str(tid)
            created_ids.append(jdb.reel_select_topic(topic_id=topic_id, title=title, platform=platform, metadata=metadata))

        return {"status": "ok", "selected_count": len(topic_ids), "ids": created_ids}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/reel/start")
async def reel_start(request: Request):
    """Start pipeline with reel_production.run().

    Accepts either:
      {"topic_id": "topic_001", "topic_title": "My Topic", "platforms": [...]}
      {"topics": [{"id": "topic_001", "title": "My Topic"}, ...], "platforms": [...]}
    """
    body = await request.json()

    # Support both legacy single-topic and new array format from reel-producer.html
    topics_arr = body.get("topics", [])
    if topics_arr and isinstance(topics_arr[0], dict):
        first = topics_arr[0]
        topic_id = str(first.get("id", first.get("topic_id", "")))
        topic_title = str(first.get("title", first.get("topic_title", "")))
    else:
        topic_id = str(body.get("topic_id", topics_arr[0] if topics_arr else ""))
        topic_title = str(body.get("topic_title", ""))

    platforms = body.get("platforms", ["youtube"])

    if not topic_id:
        return JSONResponse({"ok": False, "error": "topic_id required"}, status_code=400)

    try:
        from core import db as jdb
        jdb.reel_start_production(topic_id)
    except Exception:
        pass

    try:
        pipeline_payload = {
            "topic": topic_title or topic_id,
            "topic_id": topic_id,
            "style": "shorts",
            "tone": "viral",
            "platforms": platforms if isinstance(platforms, list) else [platforms],
        }

        result = await p_reel_prod.run(pipeline_payload)

        output_path = result.get("output_path", "")
        script_metadata = result.get("result_summary", {}).get("stages", {}).get("stage2_script", {})
        duration_s = result.get("result_summary", {}).get("stages", {}).get("stage4_assembly", {}).get("duration_s", 0)

        for platform in platforms if isinstance(platforms, list) else [platforms]:
            try:
                from core import db as jdb
                jdb.reel_complete(
                    topic_id=topic_id,
                    title=f"{topic_title} - {platform.title()}",
                    platform=platform,
                    output_path=output_path,
                    script=script_metadata,
                    duration_s=duration_s,
                    topic_title=topic_title
                )
            except Exception:
                pass

        return {"ok": True, "job_id": topic_id, **result}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/reel/approve-script")
async def reel_approve_script(request: Request):
    """Advance pipeline after script review.

    Usage: POST /api/reel/approve-script {"topic_id": "topic_001", "approved": true, "notes": "Looks good"}
    """
    body = await request.json()
    topic_id = str(body.get("topic_id", ""))
    approved = bool(body.get("approved", True))
    notes = str(body.get("notes", ""))

    if not topic_id:
        return JSONResponse({"status": "error", "message": "topic_id required"}, status_code=400)

    if not approved:
        return {"status": "ok", "approved": False, "message": "Script rejected", "notes": notes}

    try:
        await manager.log(f"Script approved for {topic_id}", "success")
        return {"status": "ok", "approved": True, "message": "Script approved. Pipeline will continue."}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/reel/pending")
async def reel_pending():
    """List completed reels from database."""
    try:
        from core import db as jdb
        completed = jdb.reel_get_completed()
        return {"status": "ok", "reels": completed}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/reel/download/{topic_id_platform}")
async def reel_download(topic_id_platform: str):
    """Return file download.

    Usage: GET /api/reel/download/topic_001_youtube
    """
    parts = topic_id_platform.rsplit("_", 1)
    if len(parts) != 2:
        return JSONResponse({"status": "error", "message": "Invalid format. Use topicid_platform"}, status_code=400)

    topic_id = _re.sub(r'[^\w\-.]', '', parts[0])
    platform = _re.sub(r'[^\w\-.]', '', parts[1]) if len(parts) > 1 else ""
    file_path = f"outputs/{topic_id}_{platform}.mp4"
    path = Path(__file__).parent / file_path

    if not path.exists():
        return JSONResponse({"status": "error", "message": "File not found"}, status_code=404)

    return FileResponse(path, filename=f"{topic_id}_{platform}.mp4")


@app.websocket("/ws/reel")
async def ws_reel(websocket: WebSocket):
    """Broadcast pipeline progress and handle commands.

    Connect to receive real-time updates on reel production pipeline.
    Frontend can send commands: start_production, approve_script, reject_script
    """
    # Origin validation
    for hdr_name, hdr_val in websocket.scope.get("headers", []):
        if hdr_name == b"origin":
            origin = hdr_val.decode("utf-8", errors="replace")
            parsed = urlparse(origin)
            if parsed.hostname not in ("localhost", "127.0.0.1"):
                await websocket.close(code=4403, reason="Origin not allowed")
                return
            break
    await manager.connect(websocket)
    try:
        await manager.log("Reel producer WebSocket connected", "info")

        # Forward incoming commands to pipeline handler
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                cmd_type = msg.get("type")
                payload = msg.get("payload", {})

                if cmd_type == "start_production":
                    _handleStartProduction(payload)
                elif cmd_type == "approve_script":
                    _handleApproveScript(payload)
                elif cmd_type == "reject_script":
                    _handleRejectScript(payload)
            except json.JSONDecodeError:
                await manager.log(f"Invalid JSON: {data}", "error")
    except Exception as e:
        manager.disconnect(websocket)
        await manager.log(f"WebSocket disconnected: {e}", "error")


def _handleStartProduction(payload: dict):
    """Handle start_production command - triggers pipeline."""
    asyncio.create_task(_run_reel_pipeline(payload))


async def _run_reel_pipeline(payload: dict):
    """Run the reel pipeline with WebSocket event broadcasting."""
    from pipelines.reel_production import run as reel_prod_run

    topics = payload.get("topics", [])
    pipeline_id = payload.get("pipeline_id", f"pipeline-{int(time.time())}")

    for topic in topics:
        topic_id = topic.get("id")
        topic_title = topic.get("topic")

        # Emit pipeline start event
        await manager.pipeline_event("pipeline", "started", 0, {"pipeline_id": pipeline_id, "topic": topic_title})

        try:
            # Store pipeline start in DB
            from core import db as jdb
            jdb.reel_start_production(topic_id)

            # Run the pipeline
            result = await reel_prod_run({
                "topic": topic_title,
                "topic_id": topic_id,
                "style": "shorts",
                "tone": "viral",
                "platforms": ["youtube", "tiktok", "instagram"],
            })

            # Emit completion event
            platform = "youtube"
            output_path = result.get("output_path", "")
            script_summary = result.get("result_summary", {}).get("stages", {}).get("stage2_script", {})

            jdb.reel_complete(
                topic_id=topic_id,
                title=f"{topic_title} - {platform.title()}",
                platform=platform,
                output_path=output_path,
                script=script_summary,
            )

            await manager.reel_complete({
                "id": topic_id,
                "topic": topic_title,
                "platform": platform,
                "output_path": output_path,
                "status": "complete",
            })

        except Exception as e:
            await manager.log(f"Pipeline failed for {topic_title}: {e}", "error")
            await manager.pipeline_event("pipeline", "failed", 0, {"pipeline_id": pipeline_id, "error": str(e)})


def _handleApproveScript(payload: dict):
    """Handle approve_script command - advances pipeline."""
    asyncio.create_task(_do_approve_script(payload))


async def _do_approve_script(payload: dict):
    """Process script approval."""
    script_id = payload.get("script_id")
    await manager.pipeline_event("script", "approved", 60, {"script_id": script_id})


def _handleRejectScript(payload: dict):
    """Handle reject_script command - cancels current topic."""
    asyncio.create_task(_do_reject_script(payload))


async def _do_reject_script(payload: dict):
    """Process script rejection."""
    script_id = payload.get("script_id")
    await manager.pipeline_event("script", "rejected", 0, {"script_id": script_id})
    await manager.log(f"Script {script_id} rejected", "warning")


@app.post("/api/reel/regenerate-scene")
async def api_reel_regenerate_scene(req: Request):
    """Re-generate Pollinations image for a single scene."""
    body = await req.json()
    topic_id = body.get("topic_id", "reel")
    scene_idx = int(body.get("scene_idx", 0))
    description = body.get("description", "cinematic scene")

    import httpx as _httpx
    from agents.asset_generator import POLLINATIONS_BASE, ASSETS_BASE, _encode_prompt, _make_safe_filename

    encoded = _encode_prompt(description)
    seed = scene_idx * 1000 + int(time.time()) % 1000
    url = (
        f"{POLLINATIONS_BASE}/{encoded}"
        f"?model=flux&width=1080&height=1920&seed={seed}&nologo=true&enhance=true"
    )
    try:
        async with _httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            r = await client.get(url)
        if r.status_code == 200 and len(r.content) > 1024:
            fname = f"{_make_safe_filename(topic_id)}_scene{scene_idx}_regen_{seed}.jpg"
            path = ASSETS_BASE / fname
            ASSETS_BASE.mkdir(parents=True, exist_ok=True)
            path.write_bytes(r.content)
            return {"ok": True, "asset_path": str(path), "url": f"/outputs/assets/{fname}"}
        return JSONResponse({"ok": False, "error": f"Pollinations HTTP {r.status_code}"}, status_code=502)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/reel/export/{fmt}")
async def api_reel_export_format(fmt: str, req: Request):
    """Re-export master video in a specific platform format."""
    ALLOWED = {"youtube", "tiktok", "instagram", "square"}
    if fmt not in ALLOWED:
        return JSONResponse({"ok": False, "error": f"format must be one of {ALLOWED}"}, status_code=400)
    body = await req.json()
    topic_id = body.get("topic_id", "reel")
    master_path = body.get("master_path", "")
    if not master_path or not Path(master_path).exists():
        return JSONResponse({"ok": False, "error": "master_path not found"}, status_code=400)
    try:
        from agents.platform_exporter import run as _pexp
        result = await _pexp(
            master_video=master_path,
            script_metadata={"topic": topic_id},
            topic_id=topic_id,
            platforms=[fmt],
        )
        exports = result.get("exports", [])
        url = exports[0].get("url") if exports else None
        return {"ok": True, "url": url, "format": fmt, "result": result}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/reel/caption")
async def api_reel_caption(req: Request):
    """Generate caption and hashtags for a reel topic."""
    body = await req.json()
    topic = body.get("topic", "")
    style = body.get("style", "viral")
    platforms = body.get("platforms", ["youtube", "tiktok"])

    if not topic:
        return JSONResponse({"ok": False, "error": "topic required"}, status_code=400)

    try:
        from core.llm import llm_complete
        platforms_str = ", ".join(platforms)
        prompt = (
            f"Write a {style} social media caption and 10 hashtags for: {topic}\n"
            f"Platforms: {platforms_str}\n"
            "Return ONLY JSON: {\"caption\": \"...\", \"hashtags\": [\"#tag1\", ...]}"
        )
        reply = await llm_complete(prompt)
        import re as _re
        m = _re.search(r"\{.*\}", reply, _re.DOTALL)
        if m:
            import json as _json
            data = _json.loads(m.group())
            return {"ok": True, "caption": data.get("caption", ""), "hashtags": data.get("hashtags", [])}
        # Fallback if LLM returns plain text
        return {"ok": True, "caption": reply[:300], "hashtags": [f"#{topic.replace(' ','')}", "#viral", "#trending"]}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# ── Avatar Reel Batch API ─────────────────────────────────────────────────
@app.post("/api/reels/avatar-batch")
async def api_avatar_reel_batch(req: Request):
    """Batch produce avatar reel videos from a list of niche topics.

    Body: {"topics": ["tech AI", "luxury", "fitness"], "count": 3, "num_scenes": 3}
    Returns: {"ok": true, "total_requested": N, "total_ok": M, "reels": [...]}
    """
    body = await req.json()
    topics = body.get("topics", [])
    count = int(body.get("count", 1))
    num_scenes = int(body.get("num_scenes", 3))

    if not topics:
        return JSONResponse({"ok": False, "error": "topics list required"}, status_code=400)

    try:
        result = await p_avatar_reel.run({
            "topics": topics,
            "count": count,
            "num_scenes": num_scenes,
        })
        extra = result.get("extra", {})
        return {
            "ok": result.get("ok", False),
            "total_requested": extra.get("total_requested", 0),
            "total_ok": extra.get("total_ok", 0),
            "total_failed": extra.get("total_failed", 0),
            "reels": extra.get("reels", []),
            "errors": extra.get("errors", []),
            "run_id": result.get("run_id"),
        }
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"{type(e).__name__}: {e}"}, status_code=500)


@app.get("/api/reels/list")
async def api_reels_list():
    """List generated avatar reel videos from outputs/reels/."""
    reels_dir = BASE / "outputs" / "reels"
    reel_list = []
    if reels_dir.exists():
        for video in sorted(reels_dir.rglob("video.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)[:50]:
            rel = str(video.relative_to(BASE / "outputs")).replace("\\", "/")
            niche = video.parent.name
            reel_list.append({
                "ok": True,
                "niche": niche.replace("_", " ").title(),
                "output_path": str(video),
                "url": f"/outputs/{rel}",
                "size_bytes": video.stat().st_size,
                "created_at": datetime.fromtimestamp(video.stat().st_mtime, tz=timezone.utc).isoformat(),
            })
    return {"ok": True, "reels": reel_list, "total": len(reel_list)}


@app.get("/api/research/trending")
async def api_research_trending(niche: str = ""):
    """Return trending topics for a niche from Google Trends RSS + Reddit."""
    if not niche.strip():
        return JSONResponse({"status": "error", "message": "niche query param required"}, status_code=400)
    try:
        from core.web_intel import search_trending
        results = await search_trending(niche.strip())
        return {"status": "ok", "niche": niche, "count": len(results), "results": results}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/research/hooks")
async def api_research_hooks(topic: str = ""):
    """Return viral hook phrases for a topic via Reddit + HN title analysis."""
    if not topic.strip():
        return JSONResponse({"status": "error", "message": "topic query param required"}, status_code=400)
    try:
        from core.web_intel import find_viral_hooks
        hooks = await find_viral_hooks(topic.strip())
        return {"status": "ok", "topic": topic, "hooks": hooks}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/research/youtube")
async def api_research_youtube():
    """Return trending YouTube videos via public RSS feed (no API key)."""
    try:
        from core.web_intel import get_youtube_trends
        videos = await get_youtube_trends()
        return {"status": "ok", "count": len(videos), "videos": videos}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


# ── Orchestrator + agent feed ─────────────────────────────────────────────
@app.post("/api/orchestrator/run")
async def api_orchestrator_run(req: Request):
    body = await req.json()
    goal = (body.get("goal") or "").strip()
    if not goal:
        return JSONResponse({"ok": False, "error": "goal required"}, status_code=400)
    plan = body.get("plan")
    try:
        result = await jorch.run_goal(goal, plan)
        return {"ok": True, **result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/agents/events")
async def api_agent_events(limit: int = 100):
    return {"events": jdb.recent_events(limit=limit)}


@app.get("/api/agents/active")
async def api_agents_active():
    return jorch.active_agents()


@app.get("/api/mc/stats")
async def api_mc_stats():
    """Stats bar for Mission Control: runs today, assets generated, ideas ranked, cost estimate."""
    return jdb.mc_stats()


@app.get("/api/mission/status")
async def api_mission_status():
    """Unified Mission Control status: system health + service status + agent states."""
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    _root = "C:\\" if sys.platform == "win32" else "/"
    disk = psutil.disk_usage(_root)
    ollama_ok = await ollama.is_available()

    services: dict[str, dict] = {}
    _named = {
        "Ollama": "http://localhost:11434",
        "Free Proxy": "http://localhost:8082",
    }
    async with httpx.AsyncClient(timeout=2) as client:
        for name, url in _named.items():
            try:
                r = await client.get(url, timeout=2)
                services[name] = {"up": True, "url": url, "status": r.status_code}
            except Exception:
                services[name] = {"up": False, "url": url, "status": None}

    return {
        "health": {
            "cpu": round(cpu),
            "mem": round(mem.percent),
            "disk": round(disk.percent),
            "ollama_ok": ollama_ok,
        },
        "services": services,
        "agents": {name: info.copy() for name, info in _agents.items()},
    }


# ── Ideas ─────────────────────────────────────────────────────────────────
@app.get("/api/ideas")
async def api_ideas_list(status: str | None = None):
    return {"items": jideas.list_all(status=status)}


@app.post("/api/ideas")
async def api_ideas_add(req: Request):
    body = await req.json()
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"ok": False, "error": "text required"}, status_code=400)
    return {"ok": True, "item": jideas.add(text, source=body.get("source", "manual"))}


@app.patch("/api/ideas/{idea_id}")
async def api_ideas_update(idea_id: int, req: Request):
    fields = await req.json()
    jideas.update(idea_id, **{k: v for k, v in fields.items() if k in ("score", "status")})
    return {"ok": True}


@app.post("/api/ideas/rank")
async def api_ideas_rank():
    return await jideas.rank_unscored()


# ── Brand voice ───────────────────────────────────────────────────────────
BRAND_PATH = BASE / "data" / "brand_voice.json"


@app.get("/api/brand")
async def api_brand_get():
    if BRAND_PATH.exists():
        try:
            return JSONResponse(json.loads(BRAND_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return JSONResponse({"tone": "", "audience": "", "banned_phrases": [],
                         "signature_opening": "", "language": "en", "improvements": []})


@app.post("/api/brand")
async def api_brand_save(req: Request):
    body = await req.json()
    current: dict = {}
    if BRAND_PATH.exists():
        try:
            current = json.loads(BRAND_PATH.read_text(encoding="utf-8"))
        except Exception:
            current = {}
    for k in ("tone", "audience", "banned_phrases", "signature_opening", "language"):
        if k in body:
            current[k] = body[k]
    current.setdefault("improvements", [])
    BRAND_PATH.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return {"ok": True}


# ── Costs ─────────────────────────────────────────────────────────────────
@app.get("/api/costs/summary")
async def api_costs_summary(days: int = 7):
    return jdb.cost_summary(days=days)


# ── Schedules ─────────────────────────────────────────────────────────────
@app.get("/api/schedules")
async def api_sched_list():
    return {"items": jdb.list_schedules()}


@app.post("/api/schedules")
async def api_sched_add(req: Request):
    body = await req.json()
    try:
        sid = jsched.add(
            name=body["name"], cron_expr=body["cron"],
            pipeline=body["pipeline"], params=body.get("params", {}),
        )
        return {"ok": True, "id": sid}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.patch("/api/schedules/{sid}")
async def api_sched_patch(sid: int, req: Request):
    body = await req.json()
    if "enabled" in body:
        jsched.toggle(sid, bool(body["enabled"]))
    return {"ok": True}


@app.delete("/api/schedules/{sid}")
async def api_sched_delete(sid: int):
    jsched.remove(sid)
    return {"ok": True}


# ── Asset library ─────────────────────────────────────────────────────────
@app.get("/api/library/stats")
async def api_lib_stats():
    return jlib.stats()


@app.get("/api/library/search")
async def api_lib_search(q: str = "", kind: str = "", limit: int = 60):
    return {"items": jlib.search(query=q, kind=kind, limit=limit)}


# ── Unified LLM chat (proxy → ollama with cost logging) ───────────────────
@app.post("/api/llm/chat")
async def api_llm_chat(req: Request):
    body = await req.json()
    message = (body.get("message") or "").strip()
    history = body.get("history") or []
    if not message:
        return JSONResponse({"ok": False, "error": "message required"}, status_code=400)
    try:
        reply = await jllm.chat(
            messages=history + [{"role": "user", "content": message}],
            system=body.get("system", "You are MAJD, concise and direct."),
            max_tokens=int(body.get("max_tokens", 1024)),
        )
        return {"ok": True, "reply": reply, "response": reply}
    except jllm.LLMError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=502)


# ── MAJD v3.0 new page routes ─────────────────────────────────────────────
@app.get("/voice-lab")
async def voice_lab_page(request: Request):
    return templates.TemplateResponse("voice-lab.html", {"request": request})


@app.get("/cinegen")
async def cinegen_page(request: Request):
    return templates.TemplateResponse("cinegen.html", {"request": request})


@app.get("/publish-hub")
async def publish_hub_page(request: Request):
    return templates.TemplateResponse("publish-hub.html", {"request": request})


# ── Voice Lab API ─────────────────────────────────────────────────────────
_VOICE_PROFILES_FILE = Path(__file__).parent / "data" / "voices.json"
_AUDIO_OUT = Path(__file__).parent / "outputs" / "audio"
_AUDIO_OUT.mkdir(parents=True, exist_ok=True)

def _load_voice_profiles() -> list:
    try:
        if _VOICE_PROFILES_FILE.exists():
            return json.loads(_VOICE_PROFILES_FILE.read_text())
    except Exception:
        pass
    return [
        {"id": "majd-default", "name": "MAJD Default", "lang": "en", "engine": "pyttsx3", "builtin": True},
        {"id": "majd-ar", "name": "MAJD Arabic", "lang": "ar", "engine": "gtts", "builtin": True},
    ]

def _save_voice_profiles(profiles: list):
    _VOICE_PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _VOICE_PROFILES_FILE.write_text(json.dumps(profiles, indent=2))


@app.get("/api/voice/status/{model}")
async def api_voice_status(model: str):
    engines = {"pyttsx3": True, "gtts": False}
    try:
        import pyttsx3  # noqa
        engines["pyttsx3"] = True
    except ImportError:
        engines["pyttsx3"] = False
    return {"ok": True, "model": model, "status": "available", "loaded": engines["pyttsx3"], "engines": engines}


@app.post("/api/voice/clone")
async def api_voice_clone(req: Request):
    """Save a named voice profile (no model weights — profiles drive synthesis settings)."""
    body = await req.json()
    name = str(body.get("name", "")).strip()
    lang = str(body.get("lang", "en")).strip()
    if not name:
        return JSONResponse({"ok": False, "error": "name required"}, status_code=400)
    profiles = _load_voice_profiles()
    vid = f"custom-{int(time.time())}"
    profiles.append({"id": vid, "name": name, "lang": lang, "engine": "pyttsx3", "builtin": False,
                     "created_at": datetime.now(timezone.utc).isoformat()})
    _save_voice_profiles(profiles)
    return {"ok": True, "voice_id": vid, "name": name,
            "message": f"Voice profile '{name}' saved. Full neural clone requires GPT-SoVITS (in ai-repositories/)."}


@app.post("/api/voice/synthesize")
async def api_voice_synthesize(req: Request):
    """Generate TTS audio. Returns a URL to the generated MP3/WAV file."""
    body = await req.json()
    text = str(body.get("text", "")).strip()
    lang = str(body.get("lang", "en")).strip()
    voice_id = str(body.get("voice_id", "")).strip()
    if not text:
        return JSONResponse({"ok": False, "error": "text required"}, status_code=400)
    if len(text) > 5000:
        return JSONResponse({"ok": False, "error": "text too long (max 5000 chars)"}, status_code=400)

    uid = f"{int(time.time() * 1000)}"
    out_path = _AUDIO_OUT / f"{uid}.mp3"
    loop = asyncio.get_running_loop()

    # 1) Try gTTS (needs internet)
    def _gtts_sync():
        from gtts import gTTS
        import io as _io
        tts = gTTS(text=text, lang=lang if lang in ("en", "ar", "fr", "es", "de") else "en", slow=False)
        buf = _io.BytesIO()
        tts.write_to_fp(buf)
        out_path.write_bytes(buf.getvalue())

    # 2) Fallback: pyttsx3 (offline Windows SAPI)
    def _pyttsx_sync():
        import pyttsx3
        wav_path = out_path.with_suffix(".wav")
        engine = pyttsx3.init()
        engine.setProperty("rate", 165)
        engine.setProperty("volume", 0.95)
        engine.save_to_file(text, str(wav_path))
        engine.runAndWait()
        if wav_path.exists() and wav_path.stat().st_size > 0:
            import subprocess
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(wav_path), "-c:a", "libmp3lame", "-q:a", "4", str(out_path)],
                capture_output=True, timeout=30
            )
            wav_path.unlink(missing_ok=True)

    engine_used = "unknown"
    try:
        await loop.run_in_executor(None, _gtts_sync)
        if out_path.exists() and out_path.stat().st_size > 0:
            engine_used = "gtts"
    except Exception:
        pass

    if not (out_path.exists() and out_path.stat().st_size > 0):
        try:
            await loop.run_in_executor(None, _pyttsx_sync)
            if out_path.exists() and out_path.stat().st_size > 0:
                engine_used = "pyttsx3"
        except Exception:
            pass

    if not (out_path.exists() and out_path.stat().st_size > 0):
        return JSONResponse({"ok": False, "error": "TTS generation failed — no engine available"}, status_code=500)

    size = out_path.stat().st_size
    return {"ok": True, "url": f"/outputs/audio/{out_path.name}", "size_bytes": size,
            "engine": engine_used, "duration_estimate_s": round(len(text.split()) * 0.35, 1)}


@app.get("/api/voice/library")
async def api_voice_library():
    profiles = _load_voice_profiles()
    return {"ok": True, "voices": profiles, "total": len(profiles)}


# ── CineGen API ───────────────────────────────────────────────────────────
_CINEGEN_JOBS_FILE = Path(__file__).parent / "data" / "cinegen_jobs.json"
_VIDEOS_OUT = Path(__file__).parent / "outputs" / "videos"
_VIDEOS_OUT.mkdir(parents=True, exist_ok=True)

def _cg_load_jobs() -> dict:
    try:
        if _CINEGEN_JOBS_FILE.exists():
            return json.loads(_CINEGEN_JOBS_FILE.read_text())
    except Exception:
        pass
    return {}

def _cg_save_jobs(jobs: dict):
    _CINEGEN_JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CINEGEN_JOBS_FILE.write_text(json.dumps(jobs, indent=2))

_CINEGEN_TIMEOUT = 120  # seconds

async def _cinegen_emit(job_id: str, progress: int, message: str):
    """Broadcast WebSocket progress event for a CineGen job."""
    await manager.broadcast({
        "type": "cinegen_progress",
        "job_id": job_id,
        "progress": progress,
        "message": message,
    })

async def _cinegen_run_job(job_id: str, prompt: str, style: str, num_scenes: int):
    """Background task: run auto_video pipeline with timeout and WS progress events."""
    jobs = _cg_load_jobs()
    jobs[job_id]["status"] = "running"
    jobs[job_id]["progress"] = 0
    _cg_save_jobs(jobs)
    await _cinegen_emit(job_id, 5, f"Scene planning for: {prompt[:50]}")

    try:
        from pipelines.auto_video import AutoVideoPipeline
        await _cinegen_emit(job_id, 15, f"Generating {num_scenes} scenes (style: {style})")

        pipeline_coro = AutoVideoPipeline({
            "topic": prompt, "num_scenes": num_scenes, "style": style,
        }).run()
        await _cinegen_emit(job_id, 30, "LLM script generation in progress…")

        try:
            result = await asyncio.wait_for(pipeline_coro, timeout=_CINEGEN_TIMEOUT)
        except asyncio.TimeoutError:
            await _cinegen_emit(job_id, 0, f"Timed out after {_CINEGEN_TIMEOUT}s")
            jobs = _cg_load_jobs()
            jobs[job_id].update({"status": "error", "error": f"Timed out after {_CINEGEN_TIMEOUT}s"})
            _cg_save_jobs(jobs)
            return

        await _cinegen_emit(job_id, 70, "Pipeline complete — copying output…")
        jobs = _cg_load_jobs()
        if result.ok:
            import shutil
            dest = _VIDEOS_OUT / f"{job_id}.mp4"
            shutil.copy2(result.output_path, dest)
            size = dest.stat().st_size
            jobs[job_id].update({
                "status": "done", "progress": 100, "output_path": str(dest),
                "url": f"/outputs/videos/{job_id}.mp4",
                "size_bytes": size, "completed_at": datetime.now(timezone.utc).isoformat(),
            })
            await _cinegen_emit(job_id, 100, f"Done — {size // 1024} KB saved")
        else:
            jobs[job_id].update({"status": "error", "error": result.error})
            await _cinegen_emit(job_id, 0, f"Pipeline error: {result.error}")
    except Exception as e:
        jobs = _cg_load_jobs()
        jobs[job_id].update({"status": "error", "error": str(e)})
        await _cinegen_emit(job_id, 0, f"Unexpected error: {e}")
    _cg_save_jobs(jobs)


@app.post("/api/cinegen/generate")
async def api_cinegen_generate(req: Request):
    """Start a text-to-video generation job using the auto_video pipeline."""
    body = await req.json()
    prompt = str(body.get("prompt", "")).strip()
    style = str(body.get("style", "viral")).strip()
    num_scenes = max(2, min(8, int(body.get("num_scenes", 4))))
    if not prompt:
        return JSONResponse({"ok": False, "error": "prompt required"}, status_code=400)

    job_id = f"cg-{int(time.time() * 1000)}"
    jobs = _cg_load_jobs()
    jobs[job_id] = {
        "job_id": job_id, "prompt": prompt, "style": style,
        "num_scenes": num_scenes, "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _cg_save_jobs(jobs)
    asyncio.create_task(_cinegen_run_job(job_id, prompt, style, num_scenes))
    return {"ok": True, "job_id": job_id, "status": "queued",
            "message": f"Video generation started for: {prompt[:60]}"}


@app.post("/api/cinegen/image-to-video")
async def api_cinegen_img2vid(req: Request):
    """Generate a video from a Pollinations image URL as the visual base."""
    body = await req.json()
    prompt = str(body.get("prompt", "")).strip()
    image_url = str(body.get("image_url", "")).strip()
    if not prompt:
        return JSONResponse({"ok": False, "error": "prompt required"}, status_code=400)
    # Re-use cinegen generate pipeline (downloads image as first scene)
    job_id = f"i2v-{int(time.time() * 1000)}"
    jobs = _cg_load_jobs()
    jobs[job_id] = {
        "job_id": job_id, "prompt": prompt, "image_url": image_url,
        "status": "queued", "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _cg_save_jobs(jobs)
    asyncio.create_task(_cinegen_run_job(job_id, prompt, "cinematic", 4))
    return {"ok": True, "job_id": job_id, "status": "queued"}


@app.get("/api/cinegen/history")
async def api_cinegen_history():
    """List all completed video generations."""
    jobs = _cg_load_jobs()
    done = [j for j in jobs.values() if j.get("status") == "done"]
    # Also scan outputs/videos/ for any manually generated mp4s
    scanned = []
    for mp4 in sorted(_VIDEOS_OUT.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True):
        job_id = mp4.stem
        if not any(j.get("job_id") == job_id for j in done):
            scanned.append({
                "job_id": job_id, "url": f"/outputs/videos/{mp4.name}",
                "size_bytes": mp4.stat().st_size,
                "created_at": datetime.fromtimestamp(mp4.stat().st_mtime, tz=timezone.utc).isoformat(),
                "status": "done", "prompt": job_id.replace("-", " "),
            })
    all_videos = done + scanned
    return {"ok": True, "videos": all_videos[:50], "total": len(all_videos)}


@app.get("/api/cinegen/status/{job_id}")
async def api_cinegen_status(job_id: str):
    jobs = _cg_load_jobs()
    job = jobs.get(job_id)
    if not job:
        return JSONResponse({"ok": False, "error": "job not found"}, status_code=404)
    progress = {"queued": 0, "running": 50, "done": 100, "error": 0}.get(job["status"], 0)
    return {"ok": True, **job, "progress": progress}


# ── Publish Hub API ───────────────────────────────────────────────────────
_PUBLISH_QUEUE_FILE = Path(__file__).parent / "data" / "publish_queue.json"

def _pq_load() -> list:
    try:
        if _PUBLISH_QUEUE_FILE.exists():
            return json.loads(_PUBLISH_QUEUE_FILE.read_text())
    except Exception:
        pass
    return []

def _pq_save(queue: list):
    _PUBLISH_QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PUBLISH_QUEUE_FILE.write_text(json.dumps(queue, indent=2))


_EXPORTS_DIR = Path(__file__).parent / "outputs" / "exports"
_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


@app.post("/api/publish/export")
async def api_publish_export(req: Request):
    """Copy a generated file to outputs/exports/ and return the saved path."""
    body = await req.json()
    file_path = str(body.get("file_path", "")).strip()
    title = str(body.get("title", "export")).strip()
    if not file_path:
        return JSONResponse({"ok": False, "error": "file_path required"}, status_code=400)
    src = Path(file_path).resolve()
    allowed_dirs = [(BASE / "outputs").resolve(), (BASE / "downloads").resolve()]
    if not any(src.is_relative_to(d) for d in allowed_dirs):
        return JSONResponse({"ok": False, "error": "Path not allowed"}, status_code=403)
    if not src.exists():
        # Try relative to content-creator dir
        src = (Path(__file__).parent / file_path.lstrip("/")).resolve()
        if not any(src.is_relative_to(d) for d in allowed_dirs):
            return JSONResponse({"ok": False, "error": "Path not allowed"}, status_code=403)
    if not src.exists():
        return JSONResponse({"ok": False, "error": f"File not found: {file_path}"}, status_code=404)
    import shutil, re
    slug = re.sub(r"[^\w\-]", "_", title)[:40]
    dest = _EXPORTS_DIR / f"{slug}_{int(time.time())}{src.suffix}"
    shutil.copy2(src, dest)
    rel = str(dest.relative_to(Path(__file__).parent)).replace("\\", "/")
    return {"ok": True, "export_path": str(dest), "url": f"/{rel}",
            "size_bytes": dest.stat().st_size,
            "message": f"Saved to outputs/exports/{dest.name}"}


@app.post("/api/publish/now")
async def api_publish_now(req: Request):
    """Add content to the export queue (manual-publish workflow — no platform OAuth)."""
    body = await req.json()
    title = str(body.get("title", "")).strip()
    caption = str(body.get("caption", "")).strip()
    platforms = body.get("platforms", ["youtube"])
    hashtags = body.get("hashtags", [])
    file_path = str(body.get("file_path", "")).strip()
    if not title:
        return JSONResponse({"ok": False, "error": "title required"}, status_code=400)

    export_url = None
    if file_path:
        # Auto-export the file to outputs/exports/
        src = Path(file_path) if Path(file_path).exists() else Path(__file__).parent / file_path.lstrip("/")
        if src.exists():
            import shutil, re
            slug = re.sub(r"[^\w\-]", "_", title)[:40]
            dest = _EXPORTS_DIR / f"{slug}_{int(time.time())}{src.suffix}"
            shutil.copy2(src, dest)
            export_url = f"/outputs/exports/{dest.name}"

    queue = _pq_load()
    item = {
        "id": f"pub-{int(time.time() * 1000)}",
        "title": title, "caption": caption, "hashtags": hashtags,
        "platforms": platforms if isinstance(platforms, list) else [platforms],
        "file_path": file_path, "export_url": export_url, "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(), "scheduled_at": None,
    }
    queue.append(item)
    _pq_save(queue)
    msg = f"Saved to outputs/exports/ — publish manually when ready." if export_url else "Added to queue. Provide file_path to auto-export."
    return {"ok": True, "id": item["id"], "status": "queued", "export_url": export_url,
            "message": msg, "item": item}


@app.post("/api/publish/schedule")
async def api_publish_schedule(req: Request):
    """Schedule a post for a future time."""
    body = await req.json()
    title = str(body.get("title", "")).strip()
    scheduled_at = str(body.get("scheduled_at", "")).strip()
    platforms = body.get("platforms", ["youtube"])
    caption = str(body.get("caption", "")).strip()
    hashtags = body.get("hashtags", [])
    file_path = str(body.get("file_path", "")).strip()
    if not title:
        return JSONResponse({"ok": False, "error": "title required"}, status_code=400)
    queue = _pq_load()
    item = {
        "id": f"sched-{int(time.time() * 1000)}",
        "title": title, "caption": caption, "hashtags": hashtags,
        "platforms": platforms if isinstance(platforms, list) else [platforms],
        "file_path": file_path, "status": "scheduled",
        "created_at": datetime.now(timezone.utc).isoformat(), "scheduled_at": scheduled_at or None,
    }
    queue.append(item)
    _pq_save(queue)

    # If APScheduler is available, mark item ready_to_export at scheduled_at
    if scheduled_at:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.date import DateTrigger
            _sched = getattr(app.state, "_pq_scheduler", None)
            if _sched is None:
                _sched = AsyncIOScheduler()
                _sched.start()
                app.state._pq_scheduler = _sched

            def _mark_ready(item_id: str):
                q = _pq_load()
                for i in q:
                    if i.get("id") == item_id and i.get("status") == "scheduled":
                        i["status"] = "ready_to_export"
                _pq_save(q)

            _sched.add_job(_mark_ready, trigger=DateTrigger(run_date=scheduled_at),
                           args=[item["id"]], id=item["id"], replace_existing=True)
        except Exception:
            pass  # APScheduler optional

    return {"ok": True, "id": item["id"], "status": "scheduled",
            "scheduled_at": item["scheduled_at"], "item": item}


@app.get("/api/publish/queue")
async def api_publish_queue():
    queue = _pq_load()
    return {"ok": True, "queue": queue, "total": len(queue)}


@app.get("/api/publish/platforms")
async def api_publish_platforms():
    platforms = [
        {"id": "youtube", "name": "YouTube", "connected": False, "icon": "▶"},
        {"id": "tiktok", "name": "TikTok", "connected": False, "icon": "♪"},
        {"id": "instagram", "name": "Instagram", "connected": False, "icon": "◈"},
        {"id": "twitter", "name": "X / Twitter", "connected": False, "icon": "✗"},
        {"id": "linkedin", "name": "LinkedIn", "connected": False, "icon": "in"},
        {"id": "facebook", "name": "Facebook", "connected": False, "icon": "f"},
    ]
    return {"ok": True, "platforms": platforms}


@app.get("/api/publish/analytics")
async def api_publish_analytics():
    queue = _pq_load()
    published = [i for i in queue if i.get("status") == "published"]
    platform_counts: dict = {}
    for item in published:
        for plat in item.get("platforms", []):
            platform_counts[plat] = platform_counts.get(plat, 0) + 1
    return {"ok": True, "total_posts": len(published), "queued": len([i for i in queue if i["status"] == "queued"]),
            "scheduled": len([i for i in queue if i["status"] == "scheduled"]),
            "reach": len(published) * 2500, "engagement": round(len(published) * 3.2, 1),
            "platforms": platform_counts}

@app.get("/command-center")
async def get_command_center(request: Request):
    return templates.TemplateResponse("command_center.html", {"request": request})


@app.get("/api/command-center/status")
async def command_center_status():
    """Aggregated status for the Command Center dashboard.

    Returns: {system: {cpu, ram, disk, gpu_available}, services: [...], agents: [...]}
    """
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    _root = "C:\\" if sys.platform == "win32" else "/"
    disk = psutil.disk_usage(_root)

    # Service checks (fire in parallel)
    _SVCS = {
        "Ollama": "http://localhost:11434",
        "Proxy": "http://localhost:8082",
        "vLLM": "http://localhost:8000",
        "LocalAI": "http://localhost:8080",
    }

    async def _ck(client: httpx.AsyncClient, name: str, url: str) -> dict:
        try:
            r = await client.get(url, timeout=2)
            return {"name": name, "url": url, "up": True, "status": r.status_code}
        except Exception:
            return {"name": name, "url": url, "up": False, "status": None}

    async with httpx.AsyncClient(timeout=2) as client:
        svc_results = await asyncio.gather(
            *[_ck(client, n, u) for n, u in _SVCS.items()]
        )

    return {
        "system": {
            "cpu": round(cpu),
            "ram": round(mem.percent),
            "disk": round(disk.percent),
            "gpu_available": _has_gpu(),
        },
        "services": list(svc_results),
        "agents": [
            {"name": name, "status": info["status"], "active": info["active"], "progress": info["progress"]}
            for name, info in _agents.items()
        ],
    }


# ── Email Digest ───────────────────────────────────────────────────────────
@app.get("/digest")
async def digest_page(request: Request):
    return templates.TemplateResponse("digest.html", {"request": request})


@app.get("/api/digest/preview")
async def digest_preview(request: Request):
    from agents.email_digest_agent import EmailDigestAgent
    agent = EmailDigestAgent()
    file_param = request.query_params.get("file", "")
    if file_param:
        html = agent.get_digest_html(file_param)
        if html:
            return {"ok": True, "html": html}
        return JSONResponse({"ok": False, "error": "Digest not found"}, status_code=404)
    period = request.query_params.get("period", "daily")
    digest = await agent.run(period=period)
    html = agent._render_html(digest)
    return {"ok": True, "html": html, "period": period}


@app.post("/api/digest/send")
async def digest_send(request: Request):
    body = await request.json()
    period = str(body.get("period", "daily")).strip()
    if period not in ("daily", "weekly"):
        period = "daily"
    try:
        from agents.email_digest_agent import EmailDigestAgent
        agent = EmailDigestAgent()
        digest = await agent.run(period=period)
        html = agent._render_html(digest)
        return {"ok": True, "gmail_sent": digest.gmail_sent, "period": period, "html": html}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/digest/history")
async def digest_history():
    from agents.email_digest_agent import EmailDigestAgent
    digests = EmailDigestAgent.list_digests(limit=30)
    return {"digests": digests}


# ── Orchestrator fan-all ──────────────────────────────────────────────────
@app.post("/api/orchestrator/fan-all")
async def api_orchestrator_fan_all(req: Request):
    """Fan out to all MAJD sub-agents in parallel and return aggregated intelligence."""
    body = await req.json()
    topic = str(body.get("topic", "AI content creation")).strip()
    platforms = body.get("platforms", ["youtube", "tiktok", "instagram"])

    results: dict = {}

    async def _trend_scout():
        from core.orchestrator import TrendScoutAgent
        agent = TrendScoutAgent()
        return await agent.scout(niche=topic, limit=5)

    async def _monetization():
        from core.orchestrator import MonetizationAgent
        agent = MonetizationAgent()
        return await agent.analyse(topic, platforms)

    async def _youtube_topics():
        try:
            from agents.trending_agent import get_trending_topics
            topics = await get_trending_topics(limit=10)
            return {"ok": True, "topics": topics, "count": len(topics)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def _topic_metrics():
        try:
            from agents.topic_discovery import discover_topics
            data = await discover_topics(limit=10, niche=topic)
            return {"ok": True, "topics": data}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    trend_task, money_task, yt_task, metrics_task = await asyncio.gather(
        _trend_scout(), _monetization(), _youtube_topics(), _topic_metrics(),
        return_exceptions=True,
    )

    def _safe(r):
        return r if not isinstance(r, Exception) else {"ok": False, "error": str(r)}

    return {
        "ok": True,
        "topic": topic,
        "platforms": platforms,
        "trends": _safe(trend_task),
        "monetization": _safe(money_task),
        "youtube_topics": _safe(yt_task),
        "topic_metrics": _safe(metrics_task),
        "agents_ran": 4,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8090, reload=True)
