# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Dialtone is a self-hosted voice-to-Obsidian system that processes audio recordings locally using AI (Whisper for transcription, Ollama for summarization) and saves formatted notes to an Obsidian vault. The system is built with FastAPI and runs in Docker containers.

## Development Commands

### Environment Setup
```bash
# Development setup (< 10 minutes)
./scripts/setup.sh
# or explicitly: ./scripts/setup.sh --development

# Production setup with configuration wizard
./scripts/setup.sh --production

# Get help and see all options
./scripts/setup.sh --help

# Manual Docker setup (development)
# 1. Generate SSL certificates for HTTPS
./scripts/generate-ssl.sh

# 2. Start all services (includes nginx with HTTPS)
docker-compose up -d
docker-compose logs -f voice-notes-api

# 3. Access via HTTPS (note: self-signed cert will show browser warning)
# https://localhost/
```

### Production Deployment
```bash
# One-command production setup with interactive wizard
./scripts/setup.sh --production

# Production management commands
docker-compose restart                 # Restart services
docker-compose logs -f                # View logs
./monitor.sh                          # Check system health
./maintenance.sh                      # Run maintenance tasks
./renew-certs.sh                      # Renew SSL certificates (if SSL enabled)

# Production configuration files
.env.prod                             # Production environment
docker-compose.yml                    # Production Docker config
nginx.conf                            # Nginx reverse proxy config
```

### HTTPS Setup
```bash
# Generate SSL certificates for development
./scripts/generate-ssl.sh

# Validate HTTPS configuration
./scripts/validate-https.sh

# Test certificate information
./scripts/generate-ssl.sh info

# Verify certificate and key match
./scripts/generate-ssl.sh verify
```

### Testing
```bash
# Run all tests with coverage
pytest tests/ -v --cov=app

# Run HTTPS-specific integration tests
pytest tests/integration/test_https_setup.py -v

# Run specific test file
pytest tests/api/test_audio.py -v

# Run single test
pytest tests/services/test_transcription.py::test_transcribe_audio_success -v

# Run tests with debugging
pytest tests/services/test_whisper_model.py -v -s
```

### Code Quality
```bash
# Format code (required before commits)
black app tests

# Sort imports
isort app tests

# Type checking
mypy app

# Run all quality checks
black app tests && isort app tests && mypy app
```

### Docker Operations
```bash
# View service logs
docker-compose logs -f voice-notes-api
docker-compose logs -f ollama

# Restart specific service
docker-compose restart voice-notes-api

# Rebuild and restart
docker-compose down
docker-compose up -d --build

# Shell into container
docker-compose exec voice-notes-api /bin/bash
```

## Architecture

### High-Level Structure
```
app/
├── main.py              # FastAPI app creation & lifespan management
├── config.py            # Logging setup
├── api/                 # API endpoints (health, audio)
├── core/                # Core infrastructure
│   ├── settings.py      # Pydantic settings with validation
│   ├── exceptions.py    # Custom exception classes
│   ├── handlers.py      # Exception handlers
│   ├── middleware.py    # Request ID & logging middleware
│   └── health/          # Health check system
└── services/            # Business logic services
    ├── audio_converter.py    # FFmpeg audio processing
    ├── whisper_model.py      # Whisper model management
    ├── transcription.py      # Transcription orchestration
    ├── ollama.py            # Ollama AI summarization
    ├── markdown_formatter.py # Obsidian markdown generation
    └── upload.py            # File upload handling
```

### Service Layer Pattern
The application uses a layered architecture where:
- **API Layer** (`app/api/`) handles HTTP requests/responses
- **Service Layer** (`app/services/`) contains business logic
- **Core Layer** (`app/core/`) provides infrastructure utilities

Services are designed to be:
- Async-first with proper resource management
- Stateless with dependency injection
- Testable with clear interfaces
- Error-handling with custom exceptions

### Key Architectural Decisions

**Settings Management**: Uses Pydantic with environment validation. Settings are centralized in `app/core/settings.py` with field validation and automatic directory creation.

**Error Handling**: Custom exception hierarchy in `app/core/exceptions.py` with specialized handlers in `app/core/handlers.py`. All services raise typed exceptions that map to appropriate HTTP responses.

**Resource Management**: Services use async context managers for cleanup (e.g., Whisper model loading, Ollama connections). The FastAPI lifespan handles service initialization and shutdown.

**Processing Pipeline**: Audio processing follows this flow:
1. Upload validation and storage (`upload.py`)
2. Audio format conversion (`audio_converter.py`) 
3. Whisper transcription (`whisper_model.py`, `transcription.py`)
4. Ollama summarization (`ollama.py`)
5. Markdown formatting (`markdown_formatter.py`)
6. Obsidian vault saving

**Container Architecture**: Two-service Docker setup:
- `voice-notes-api`: FastAPI app with Whisper models
- `ollama`: Separate AI service for summarization
- Shared network with health checks and resource limits

## Configuration

### Environment Variables
Key settings are configured via environment variables (see `app/core/settings.py`):

```bash
# Core paths
OBSIDIAN_VAULT_PATH=/path/to/vault  # Required for local development

# Processing limits
MAX_UPLOAD_SIZE=52428800            # 50MB default
PROCESSING_TIMEOUT=35               # seconds
MAX_CONCURRENT_REQUESTS=3

# AI services
WHISPER_MODEL_SIZE=base             # tiny|base|small|medium|large
OLLAMA_MODEL=llama2:7b              # AI model for summarization
OLLAMA_ENABLED=true                 # Enable/disable summarization
```

### Testing Configuration
Tests use environment variable `TESTING=true` to skip directory validation and external service dependencies. Test files are organized to mirror the app structure.

## Development Workflow

### Branch Strategy
- Main development on `feature/issue-1-docker-fastapi-setup`
- Feature branches: `feature/issue-{number}-{description}`
- Use conventional commits: `feat:`, `fix:`, `test:`, `docs:`

### Quality Requirements
- Black formatting (88 character lines)
- isort import sorting  
- mypy type checking
- Minimum 80% test coverage
- All tests must pass before merge

### Testing Strategy
- Unit tests for individual services
- Integration tests for full workflows
- Mock external dependencies (Ollama, file system)
- Test error conditions and edge cases
- Use pytest fixtures for common setup

## Common Issues

### Whisper Model Loading
The Whisper model is pre-downloaded in the Docker image, but first-time local runs may be slow. Models are cached in the container.

### Ollama Service Communication
The API depends on the Ollama service being healthy. Check `docker-compose logs ollama` if summarization fails. The service has a 120s startup period for model loading.

### File Permissions
The Docker container runs as non-root user `appuser`. Ensure the Obsidian vault path has appropriate permissions for Docker volume mounts.

### Memory Usage
Whisper models require significant memory. The `base` model needs ~1GB RAM. Adjust Docker resource limits in `docker-compose.yml` if needed.