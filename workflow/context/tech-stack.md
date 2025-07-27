# Technology Stack

## Frontend
- **Core**: Vanilla JS + Web APIs (MediaRecorder)
- **UI**: HTML/CSS (no framework)
- **PWA**: Service Worker + IndexedDB
- **Future**: React Native for native app

## Backend
- **API**: FastAPI (Python 3.11+)
- **Server**: Uvicorn
- **Queue**: AsyncIO (Redis for scale)
- **AI**: Whisper (base) + Ollama (Llama2/Mistral)

## Infrastructure
- **Containers**: Docker Compose
  - voice-notes-api
  - ollama
  - nginx (SSL)
- **Storage**: Local filesystem
- **Networking**: Nginx reverse proxy + Let's Encrypt

## Development
- **Languages**: Python 3.11+, ES2020+ JS
- **Quality**: Black, mypy, ESLint
- **Testing**: pytest, 80% coverage
- **CI/CD**: GitHub Actions → Docker

## Patterns
- **Backend**: Layered architecture, async/await
- **Frontend**: Offline-first, module pattern
- **Security**: Input validation, least privilege
- **Deployment**: Blue-green, health checks