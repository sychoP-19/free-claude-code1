@echo off
setlocal EnableDelayedExpansion
title EMPIRE OS  ^|  Proxy Launcher v5
color 0A

echo.
echo  ================================================
echo   EMPIRE OS  -  Proxy Launcher v5
echo   Repo: C:\Users\Admin\Desktop\free-claude-code
echo  ================================================
echo.

set "REPO=C:\Users\Admin\Desktop\free-claude-code"
set "LOG=%REPO%\proxy-launch.log"

:: ── PRE-FLIGHT CHECKS ─────────────────────────────────────────
echo  [1/6] Running pre-flight checks...

:: Check repo exists
if not exist "%REPO%\server.py" (
    echo  [FATAL] server.py not found at: %REPO%
    echo  Expected: %REPO%\server.py
    pause & exit /b 1
)
echo     server.py   ... OK

:: Check runtime.py exists
if not exist "%REPO%\api\runtime.py" (
    echo  [FATAL] api\runtime.py not found at: %REPO%
    pause & exit /b 1
)
echo     runtime.py  ... OK

:: Check for patches
findstr /c:"PATCHED-EMPIRE" "%REPO%\api\runtime.py" >nul 2>&1
if errorlevel 1 (
    echo     patches    ... WARNING: runtime.py may not be patched.
    echo     Run PATCH.bat first, or patches may have been reverted.
) else (
    echo     patches    ... OK (PATCHED-EMPIRE markers found)
)

:: Check UV is available
where uv >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] 'uv' not found in PATH.
    echo  Install it: https://docs.astral.sh/uv/getting-started/installation/
    pause & exit /b 1
)
echo     uv tool    ... OK

:: Check git (optional, for updates)
where git >nul 2>&1
if errorlevel 1 (
    echo     git        ... NOT FOUND (skipping auto-update)
    set "GIT_OK=0"
) else (
    echo     git        ... OK
    set "GIT_OK=1"
)

:: Check .env, write if missing or stale
if not exist "%REPO%\.env" (
    echo     .env       ... NOT FOUND — will create
    set "ENV_NEEDS_WRITE=1"
) else (
    findstr /c:"NVIDIA_NIM_API_KEY=" "%REPO%\.env" >nul 2>&1
    if errorlevel 1 (
        echo     .env       ... FOUND but missing keys — will overwrite
        set "ENV_NEEDS_WRITE=1"
    ) else (
        echo     .env       ... OK
    )
)

echo.

:: ── UPDATE REPO ───────────────────────────────────────────────
if "!GIT_OK!"=="1" (
    echo  [2/6] Pulling latest changes...
    cd /d "%REPO%"
    git pull origin main 2>&1 | findstr /v "^$"
    if errorlevel 1 (
        echo  [WARN] git pull failed — using local version.
    ) else (
        echo  [OK] Repository updated.
        echo  [WARN] If patches were applied to old files, re-run PATCH.bat!
        echo          (Patches may need re-application after git pull)
    )
) else (
    echo  [2/6] Skipping git update (git not found).
)
echo.

:: ── WRITE .ENV ────────────────────────────────────────────────
if defined ENV_NEEDS_WRITE (
    echo  [3/6] Writing .env file...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$p = '%REPO%\.env';" ^
        "$k = @{" ^
        "  'NVIDIA_NIM_API_KEY' = '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';" ^
        "  'OPENROUTER_API_KEY' = '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';" ^
        "  'GLM_API_KEY' = '74bacd776f0d4562978ccb435b99920b.dlNNEUIixvAJzn08y2nZSkGS';" ^
        "  'KIMI_API_KEY' = 'sk-sO2pJuGm0RXWUrcw86aWu95SI9fZMdwhk8TBzQFhYDesU09R';" ^
        "  'DEEPSEEK_API_KEY' = '';" ^
        "  'ANTHROPIC_AUTH_TOKEN' = 'freecc';" ^
        "  'ANTHROPIC_BASE_URL' = 'http://localhost:8082';" ^
        "  'PORT' = '8082';" ^
        "  'HOST' = '0.0.0.0';" ^
        "  'MODEL_OPUS' = 'nvidia_nim/moonshotai/kimi-k2.6';" ^
        "  'MODEL_SONNET' = 'nvidia_nim/z-ai/glm5';" ^
        "  'MODEL_HAIKU' = 'nvidia_nim/meta/llama-3.1-8b-instruct';" ^
        "  'MODEL' = 'nvidia_nim/moonshotai/kimi-k2.6';" ^
        "  'BACKUP_OPUS_PROVIDERS' = 'nvidia_nim,open_router';" ^
        "  'BACKUP_SONNET_PROVIDERS' = 'nvidia_nim,open_router';" ^
        "  'BACKUP_HAIKU_PROVIDERS' = 'nvidia_nim,open_router';" ^
        "  'ENABLE_MODEL_DISCOVERY' = 'false';" ^
        "  'SYNCHRONOUS_MODEL_DISCOVERY' = 'false';" ^
        "  'DISABLE_PROVIDER_HEALTH_CHECKING' = 'true';" ^
        "  'ENABLE_AUTO_FAILOVER' = 'true';" ^
        "  'FAILOVER_RETRY_COUNT' = '3';" ^
        "  'FAILOVER_RETRY_DELAY_MS' = '1000';" ^
        "  'CIRCUIT_BREAKER_FAILURE_THRESHOLD' = '5';" ^
        "  'CIRCUIT_BREAKER_RECOVERY_TIMEOUT_MS' = '30000';" ^
        "  'PROVIDER_RATE_LIMIT' = '30';" ^
        "  'PROVIDER_RATE_WINDOW' = '60';" ^
        "  'PROVIDER_MAX_CONCURRENCY' = '5';" ^
        "  'NVIDIA_NIM_RATE_LIMIT' = '40';" ^
        "  'NVIDIA_NIM_RATE_WINDOW' = '60';" ^
        "  'OPENROUTER_RATE_LIMIT' = '20';" ^
        "  'OPENROUTER_RATE_WINDOW' = '60';" ^
        "  'HTTP_READ_TIMEOUT' = '600';" ^
        "  'HTTP_WRITE_TIMEOUT' = '120';" ^
        "  'HTTP_CONNECT_TIMEOUT' = '60';" ^
        "  'ENABLE_MODEL_THINKING' = 'false';" ^
        "  'ENABLE_OPUS_THINKING' = 'false';" ^
        "  'ENABLE_SONNET_THINKING' = 'false';" ^
        "  'ENABLE_HAIKU_THINKING' = 'false';" ^
        "  'NVIDIA_NIM_PROXY' = '';" ^
        "  'OPENROUTER_PROXY' = '';" ^
        "  'MESSAGING_PLATFORM' = 'none';" ^
        "  'LOG_API_ERROR_TRACEBACKS' = 'true';" ^
        "  'DEBUG_PLATFORM_EDITS' = 'false';" ^
        "  'LOG_RAW_API_PAYLOADS' = 'false';" ^
        "  'LOG_RAW_SSE_EVENTS' = 'false';" ^
        "};" ^
        "$lines = ($k.GetEnumerator() | ForEach-Object { ""$($_.Key)=$($_.Value)"" });" ^
        "[System.IO.File]::WriteAllText($p, ($lines -join \"`n\") + \"`n\", [System.Text.Encoding]::UTF8)"
    echo  [OK] .env written with all keys.
) else (
    echo  [3/6] .env already present and has keys — keeping existing.
)
echo.

:: ── CHECK .env HAS CRITICAL KEYS ─────────────────────────────
echo  [4/6] Validating .env...
python -c "
import os
env_path = r'%REPO%\.env'
required = ['NVIDIA_NIM_API_KEY','OPENROUTER_API_KEY','MODEL','PORT']
missing = [k for k in required if not any(k in line for line in open(env_path) if '=' in line)]
if missing:
    print(f'  [ERROR] Missing keys: {missing}')
    exit(1)
print('  [OK] All required .env keys present.')
"
if errorlevel 1 (
    echo  [FATAL] .env validation failed. Check your .env file.
    pause & exit /b 1
)
echo.

:: ── LAUNCH ─────────────────────────────────────────────────────
echo  [5/6] Starting proxy...
echo.
echo  ================================================
echo   PROXY STARTING
echo   URL  : http://localhost:8082
echo   Docs : http://localhost:8082/docs
echo   Admin: http://localhost:8082/admin  (token: freecc)
echo  ================================================
echo.
echo  [INFO] Keep this window open. Logs appear below.
echo  [INFO] Press Ctrl+C to stop.
echo.

cd /d "%REPO%"

:: Try official fcc-server first
echo  Attempting fcc-server install (official method)...
uv tool install --force --quiet git+https://github.com/Alishahryar1/free-claude-code.git >nul 2>&1

if !errorlevel! equ 0 (
    echo  [OK] fcc-server installed. Launching...
    echo.
    fcc-server
    goto :proxy_exit
)

echo  [WARN] fcc-server unavailable. Falling back to uvicorn...
echo.

:: Fallback: uvicorn with lifespan disabled (avoids startup crash)
uv run uvicorn server:app ^
    --host 0.0.0.0 ^
    --port 8082 ^
    --lifespan off ^
    --log-level info ^
    --timeout-graceful-shutdown 30 ^
    --access-log ^
    --no-use-colors

if errorlevel 1 (
    echo.
    echo  [ERROR] uvicorn exited with error code %errorlevel%.
    echo  Check the output above for details.
    echo  Log saved to: %LOG%
)

:proxy_exit
echo.
echo  ================================================
echo   Proxy stopped.
echo  ================================================
echo.
choice /c RrQq /m "Restart (R) or Quit (Q)?"
if errorlevel 3 exit /b 0
if errorlevel 1 goto start