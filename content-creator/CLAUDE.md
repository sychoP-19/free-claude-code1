# JARVIS Content Intelligence System

## Environment Setup

### Prerequisites

- Python 3.12+ with `uv` package manager
- Node.js 18+ (for some frontend tools)
- Git for repository cloning
- FFmpeg for video processing
- Ollama for local LLM support (optional but recommended)

### Installation Steps

1. **Clone the repository** (if not already part of free-claude-code):
   ```bash
   git clone https://github.com/your-repo/free-claude-code.git
   cd free-claude-code
   ```

2. **Install dependencies**:
   ```bash
   # Install Python dependencies
   uv sync
   
   # Install additional tools if needed
   uv pip install gTTS>=2.5.1 moviepy>=1.0.3
   ```

3. **Environment Variables Setup**:
   Create a `.env` file in the `content-creator/` directory with the following variables:
   
   ```env
   # API Keys
   FAL_KEY=your_fal_api_key_here
   OPENAI_API_KEY=your_openai_api_key_here  # Optional for Whisper fallback
   
   # Ollama Configuration
   OLLAMA_BASE_URL=http://localhost:11434
   
   # OAuth for Gmail integration
   GOOGLE_CLIENT_ID=your_google_client_id
   GOOGLE_CLIENT_SECRET=your_google_client_secret
   
   # Portfolio settings
   WHATSAPP_NUMBER=+1234567890
   PORTFOLIO_SECRET=your_portfolio_secret_key
   
   # Whisper server (if using custom Whisper)
   WHISPER_SERVER=http://localhost:9000
   ```

4. **Directory Structure Setup**:
   Ensure the following directories exist:
   ```
   content-creator/
   ├── agents/
   ├── core/
   ├── data/
   ├── integrations/
   ├── outputs/
   │   ├── auto_video/
   │   ├── videos/
   │   ├── audio/
   │   ├── carousel/
   │   ├── assets/
   │   └── exports/
   ├── pipelines/
   ├── static/
   ├── templates/
   └── tests/
   ```

### Configuration

- **JARVIS_API_KEY**: Required for authentication (set to any secure string in production)
- **Port Configuration**: JARVIS runs on port 8090 by default
- **Model Configuration**: Uses the free-claude-code proxy at http://localhost:8082 by default

## Testing Procedures

### Unit Testing

- All agent classes should have 80%+ test coverage
- Core business logic functions must be tested with various input scenarios
- Edge cases should be covered in tests
- Mock external dependencies to ensure consistent test environments

### Integration Testing

- End-to-end testing of agent workflows
- API integration testing for all external service connections
- Database interaction tests for content storage and retrieval
- Test data validation and error handling scenarios

### Test Structure
1. **Unit Tests**: Test individual agent functionality in isolation
2. **Integration Tests**: Test agent coordination and data flow between components
3. **E2E Tests**: Full workflow testing from input to output
4. **Performance Tests**: Validate system performance under load
5. **Security Tests**: Validate authentication, input validation, and data protection

### Testing Framework
- Use pytest for test execution
- Structure tests with proper fixtures and test data
- Mock external APIs and services to ensure consistent testing
- Validate all input/output handling
- Test error conditions and edge cases

### Test Data Management
- Use factory functions to create consistent test data
- Maintain separate test databases for isolation
- Version control test fixtures and clean up after tests
- Use pytest fixtures for consistent setup/teardown

### Continuous Integration
- Automated testing on every commit
- Separate test environments for different testing layers
- Code coverage reports required for all changes
- Performance benchmarks for content generation tasks

### Running Tests

```bash
# From content-creator/ directory
uv run pytest tests/ -q

# Run specific test file
uv run pytest tests/test_stages.py -v

# Run tests with coverage
uv run pytest --cov=. --cov-report=html tests/
```

Pytest configuration in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"   # required for async def test_* functions
pythonpath = ["."]
testpaths = ["tests"]
```

## Deployment Instructions

### Local Development Deployment

1. **Start the application**:
   ```bash
   # From the free-claude-code root directory
   uv run uvicorn content-creator.app:app --host 0.0.0.0 --port 8090 --reload
   ```

2. **Access the application**:
   - Open browser to http://localhost:8090
   - WebSocket connection should establish automatically
   - Verify dashboard loads with HTTP 200

### Production Deployment

1. **Environment Setup**:
   - Set `JARVIS_API_KEY` environment variable for authentication
   - Configure all required API keys in `.env` file
   - Ensure all required services (Ollama, FFmpeg, etc.) are installed

2. **Run without reload for production**:
   ```bash
   uv run uvicorn content-creator.app:app --host 0.0.0.0 --port 8090 --workers 4
   ```

3. **Using a process manager (systemd)**:
   ```ini
   [Unit]
   Description=JARVIS Content Intelligence System
   After=network.target

   [Service]
   User=your-user
   WorkingDirectory=/path/to/free-claude-code
   ExecStart=/path/to/uv run uvicorn content-creator.app:app --host 0.0.0.0 --port 8090
   Restart=always
   Environment=JARVIS_API_KEY=your-secure-api-key

   [Install]
   WantedBy=multi-user.target
   ```

### Standalone Mode

For a simplified version without server dependencies:
- Open `content-creator/JARVIS.html` directly in a browser
- Works with Pollinations.ai for free image generation
- Limited functionality compared to full server mode

### Verification Checklist

After deployment, verify the following:

1. `http://localhost:8090` — dashboard loads (HTTP 200)
2. WebSocket connects (green dot in topbar)
3. Mic button → browser mic permission → speak → text appears in chat
4. Chat → JARVIS responds (English or Arabic) + voice speaks back
5. Language dropdown → switch to AR → speak Arabic → JARVIS replies in Arabic
6. `GET /api/trending/topics` → JSON with 10+ topics
7. `GET /api/github/trending` → JSON with repos
8. `GET /api/repos/services` → JSON with Ollama/proxy status (responds in ~2s)
9. `/github-hub` → trending repos grid loads
10. `/skills` → 3 tabs work (calendar, revenue, alerts)
11. Open `JARVIS.html` directly → Pollinations free image gen works
12. `POST /api/voice/synthesize {"text":"Hello","lang":"en"}` → MP3 URL returned
13. `POST /api/cinegen/generate {"prompt":"AI tools 2025"}` → job_id returned; poll status → done + MP4 > 100KB
14. `POST /api/publish/now {"title":"Test","platforms":["youtube"]}` → queued item returned
15. `POST /api/orchestrator/fan-all {"topic":"AI tools"}` → trends + monetization + youtube_topics

### Monitoring

Monitor the application using:
- Built-in logging and metrics dashboard at `/metrics`
- WebSocket event stream for real-time agent updates
- File system monitoring for output directories
- Process monitoring for uvicorn workers
