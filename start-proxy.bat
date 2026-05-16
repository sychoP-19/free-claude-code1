@echo off
REM free-claude-code proxy launcher
REM Clears corrupted proxy/key env vars, kills any old instance on port 8082, then starts fresh.

REM ── Kill any existing process on port 8082 ──────────────────────────────────
echo Checking port 8082...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8082 "') do (
    echo   Killing old process PID %%a on port 8082
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

REM ── Clear corrupted env vars (previous broken install left junk values) ──────
set OPENROUTER_API_KEY=
set NVIDIA_NIM_API_KEY=
set OPENROUTER_PROXY=
set NVIDIA_NIM_PROXY=
set LMSTUDIO_PROXY=
set LLAMACPP_PROXY=
set KIMI_PROXY=
set DEEPSEEK_API_KEY=
set KIMI_API_KEY=

echo Starting free-claude-code proxy on port 8082...
echo Claude Code endpoint: http://localhost:8082
echo Auth token:           freecc
echo Model picker:         enabled (CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1)
echo.

cd /d "%~dp0"
uv run uvicorn server:app --host 0.0.0.0 --port 8082
