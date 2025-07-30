# Dialtone API Documentation

Self-hosted voice-to-Obsidian system with local AI processing. Record audio on any device, process locally with Whisper AI, and save organized notes directly to your Obsidian vault.

## Quick Start

1. **[Deployment Guide](deployment/docker-setup.md)** - Get Dialtone running in minutes
2. **[API Reference](api/README.md)** - Complete endpoint documentation
3. **[Interactive Docs](http://localhost:8000/docs)** - Try the API live (when running)

## Architecture

```
📱 Mobile/Web → 🐳 Docker → 🧠 Whisper AI → 📝 Obsidian Vault
```

- **Frontend**: Mobile PWA with offline support
- **Backend**: FastAPI with async processing
- **AI**: Local Whisper transcription + Ollama summarization
- **Storage**: Direct Obsidian vault integration

## Core Features

- ✅ **Audio Upload** - WebM, M4A, MP3 (up to 50MB)
- ✅ **Local Transcription** - Whisper AI processing
- 🚧 **AI Summarization** - Ollama integration (coming soon)
- 🚧 **Obsidian Integration** - Direct vault saving (coming soon)
- ✅ **Health Monitoring** - System metrics and service status
- ✅ **Docker Deployment** - One-command setup

## Performance Targets

- Process 5-minute audio in <35 seconds
- 95%+ transcription accuracy
- <16GB RAM usage
- API response <500ms

---

**Need help?** Check our [troubleshooting guide](deployment/troubleshooting.md) or [open an issue](https://github.com/strouddm/dialtone/issues).