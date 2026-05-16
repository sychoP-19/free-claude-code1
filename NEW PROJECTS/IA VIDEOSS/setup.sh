#!/usr/bin/env bash
# AI Avatar Video Agent - Setup (Linux/macOS)

set -e

echo "========================================"
echo " AI Avatar Video Agent - Setup"
echo "========================================"
echo

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python3 not found. Install Python 3.10+"
    exit 1
fi

# Create venv
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Check FFmpeg
if ! command -v ffmpeg &>/dev/null; then
    echo "[WARNING] FFmpeg not found. Install via your package manager."
    echo "  Ubuntu/Debian: sudo apt install ffmpeg"
    echo "  macOS: brew install ffmpeg"
fi

# Check Ollama
if ! command -v ollama &>/dev/null; then
    echo "[WARNING] Ollama not found. Install from https://ollama.com"
    echo "  Then run: ollama pull mistral:7b"
fi

# Create directories
mkdir -p data output temp models assets

echo
echo "========================================"
echo " Setup complete!"
echo " Run: python main.py --serve"
echo " Or:  python main.py 'Your video topic'"
echo "========================================"
