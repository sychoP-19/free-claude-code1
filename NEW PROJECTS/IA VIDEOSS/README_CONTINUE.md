# Fruit Crusaders: Shattered Hearts Video Generation System

## Project Overview
This system generates cinematic anime-style videos for the "Fruit Crusaders: Shattered Hearts" project using a 7-layer AI video generation architecture.

## Current Implementation Status
The system has been architecturally implemented with all necessary components:
- Custom character configurations for 5 unique fruit characters
- Content generation skill with anime trailer script generation
- Visual asset creation with enhancement pipeline
- Full 7-layer architecture integration

## To Continue in Next Session

### 1. Install Dependencies
```bash
# Install PyTorch and other required packages
uv pip install torch transformers diffusers

# Or if using pip directly:
pip install torch transformers diffusers
```

### 2. Download Required Models
```bash
# Start Ollama if not running
ollama serve

# Pull required models
ollama pull llama3.1
ollama pull zeroscope  # For video generation (if available)
```

### 3. Run the Demo
```bash
# Run a simple character transformation demo
uv run python main.py --topic "Fruit Crusaders Transformation" --duration 30 --language en

# Run full cinematic trailer
uv run python main.py --topic "Fruit Crusaders: Shattered Hearts" --duration 60 --language en
```

### 4. System Components Ready
- Character configurations: `config.yaml`
- Content generation: `skills/fruit_crusaders_content.py`
- Visual assets: `skills/fruit_crusaders_visual_assets.py`
- Enhancement settings: `docs/fruit_crusaders_enhancement.md`

### 5. Troubleshooting Tips
- Ensure Ollama service is running: `ollama serve`
- Check that all dependencies are installed: `pip list | grep -E "(torch|transformers|diffusers)"`
- Verify GPU support if available for faster processing