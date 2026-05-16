@echo off
echo Starting Fruit Crusaders Video Generation System...
echo.

REM Start Ollama service
echo Starting Ollama service...
start ollama serve
timeout /t 5 /nobreak >nul

REM Run a simple test
echo Running Fruit Crusaders transformation demo...
uv run python main.py --topic "Fruit Crusaders Transformation" --duration 30 --language en

echo.
echo Demo run complete. Check the output folder for results.
pause