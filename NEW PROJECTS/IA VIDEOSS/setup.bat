@echo off
echo ========================================
echo  AI Avatar Video Agent - Setup
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ from python.org
    pause
    exit /b 1
)

:: Create venv
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

:: Activate venv
call .venv\Scripts\activate.bat

:: Install dependencies
echo Installing Python dependencies...
pip install -r requirements.txt

:: Check FFmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] FFmpeg not found. Install FFmpeg and add to PATH.
    echo Download from: https://ffmpeg.org/download.html
)

:: Check Ollama
ollama --version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Ollama not found. Install Ollama for local LLM.
    echo Download from: https://ollama.com
    echo Then run: ollama pull mistral:7b
)

:: Create data directories
if not exist "data" mkdir data
if not exist "output" mkdir output
if not exist "temp" mkdir temp
if not exist "models" mkdir models
if not exist "assets" mkdir assets

echo.
echo ========================================
echo  Setup complete!
echo  Run: python main.py --serve
echo  Or:  python main.py "Your video topic"
echo ========================================
pause
