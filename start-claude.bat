@echo off
REM ═══════════════════════════════════════════════════════════════════════════
REM  EMPIRE OS  ·  start-claude.bat  ·  Run AFTER start-proxy.bat
REM ═══════════════════════════════════════════════════════════════════════════

REM Bust the gateway model cache so /model shows fresh results every time
set GATEWAY_CACHE=%USERPROFILE%\.claude\cache\gateway-models.json
if exist "%GATEWAY_CACHE%" (
    del /f /q "%GATEWAY_CACHE%" >nul 2>&1
    echo   Model cache cleared.
)

REM Point Claude Code at the local proxy
set ANTHROPIC_BASE_URL=http://localhost:8082
set ANTHROPIC_AUTH_TOKEN=freecc
set CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1

echo.
echo  EMPIRE OS  ^|  Claude Code  -^>  free-claude-code proxy
echo  Endpoint  : http://localhost:8082
echo  Auth      : freecc
echo  Discovery : ON  (cache cleared)
echo  Models    : all NIM + all OpenRouter via /model picker
echo.

cd /d "C:\Users\Admin\Desktop\free-claude-code"
claude
