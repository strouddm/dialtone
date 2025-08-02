# Dialtone - Voice to Obsidian

Self-hosted voice-to-Obsidian system with local AI processing.

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+
- 6+ CPU cores, 16GB RAM
- Obsidian vault directory

### Setup (< 10 minutes)

1. Clone the repository:
```bash
git clone <repository-url>
cd dialtone
```

2. Run the setup script:
```bash
./scripts/setup.sh
```

3. Configure your Obsidian vault path:
```bash
# Edit .env file
OBSIDIAN_VAULT_PATH=/path/to/your/obsidian/vault
```

4. Restart services:
```bash
docker-compose restart
```

## Usage

### Web Interface
1. Open http://localhost:8000 in your mobile browser
2. Tap the record button to start recording
3. Speak your voice note (up to 50MB/5 minutes)
4. Stop recording when finished
5. Review and edit the transcription, summary, and keywords
6. Save to your Obsidian vault

### Edit Screen Features
- **Transcription Editing**: Edit the AI-generated transcription with mobile-friendly text input
- **Summary Management**: Add, edit, or remove bullet points from the AI summary
- **Keyword Tags**: Modify extracted keywords or add your own
- **Live Preview**: See the final markdown format before saving
- **Auto-save**: Drafts are automatically saved every 10 seconds
- **Session Recovery**: Resume editing after browser refresh or interruption

### API Documentation
- **Interactive Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **View Logs**: `docker-compose logs -f`

## Development

### Running Tests
```bash
pytest tests/ -v --cov=app
```

### Code Quality
```bash
black app tests
mypy app
```

### Project Structure
```
dialtone/
├── app/              # FastAPI application
│   ├── api/         # API endpoints
│   ├── core/        # Core functionality
│   └── main.py      # Application entry
├── tests/           # Test suite
├── docker-compose.yml
└── Dockerfile
```

## Troubleshooting

### API not responding
```bash
# Check logs
docker-compose logs voice-notes-api

# Restart services
docker-compose down
docker-compose up -d
```

### Memory issues
Edit `docker-compose.yml` to adjust resource limits:
```yaml
deploy:
  resources:
    limits:
      memory: 4G  # Increase as needed
```

## Features

- [x] Docker environment setup
- [x] FastAPI with health checks
- [ ] Audio upload endpoint
- [ ] Whisper transcription
- [ ] Ollama summarization
- [ ] Obsidian integration
- [ ] PWA frontend

## Performance Targets

- Setup time: < 30 minutes
- Processing: < 35s for 5-min audio
- Accuracy: > 95% transcription
- Uptime: > 99.9%