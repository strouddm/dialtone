# 🎵 Dialtone - Voice to Obsidian PWA

**Complete self-hosted voice-to-Obsidian system with local AI processing**

Transform your voice recordings into formatted Obsidian notes using AI transcription and summarization—all processed locally on your own hardware with no cloud dependencies.

## ✨ Features

🎤 **PWA Voice Recording** - Professional mobile app experience with offline support  
🤖 **Local AI Processing** - Whisper transcription + Ollama summarization (no cloud required)  
📝 **Smart Note Generation** - Auto-generated transcripts, summaries, and keyword tags  
💾 **Draft Management** - Auto-save, session recovery, and edit-before-save  
🔒 **Privacy First** - All processing happens locally, your data never leaves your server  
📱 **Mobile Optimized** - Install as PWA on any device, works offline  
⚡ **Fast Setup** - One command gets you running in under 10 minutes  

## 🚀 Quick Start (10 minutes)

### Prerequisites
- **Docker & Docker Compose** (20.10+)
- **8GB+ RAM** (for AI models)
- **10GB+ disk space**
- **Obsidian vault directory**

### One-Command Setup

```bash
# Clone repository
git clone <repository-url>
cd dialtone

# Run automated setup (includes SSL certificates)
./scripts/setup.sh
```

**That's it!** The setup script will:
- ✅ Validate your system requirements
- ✅ Generate SSL certificates for HTTPS/PWA
- ✅ Build and start all services (nginx, API, AI)
- ✅ Pre-download AI models
- ✅ Run health checks

### Configure Your Vault

Edit the generated `.env` file:
```bash
# Set your Obsidian vault path
OBSIDIAN_VAULT_PATH=/path/to/your/obsidian/vault
```

Then restart:
```bash
docker-compose restart
```

## 📱 Using Dialtone

### 1. Web Access
Open **https://localhost** in any browser
- ⚠️ **First time**: Click "Advanced" → "Proceed to localhost" (self-signed certificate)
- 🔒 **Why HTTPS?** Required for PWA microphone access and installation

### 2. PWA Installation (Recommended)
**Mobile:**
- **iOS Safari**: Share button → "Add to Home Screen"
- **Android Chrome**: Menu → "Add to Home Screen" or "Install App"

**Desktop:**
- Look for install icon in address bar

### 3. Recording Workflow
1. 🎤 **Record**: Tap the record button
2. 🗣️ **Speak**: Up to 5 minutes (50MB limit)
3. ✏️ **Edit**: Review AI-generated transcript, summary, keywords
4. 💾 **Save**: Note appears instantly in your Obsidian vault

### 4. Edit Screen Features
- **Smart Text Editing**: Mobile-friendly transcript editor
- **Summary Management**: Add/remove bullet points  
- **Keyword Tags**: AI-suggested tags + manual additions
- **Live Preview**: See final markdown before saving
- **Auto-save Drafts**: Every 10 seconds
- **Session Recovery**: Resume after interruption

## 🏗️ System Architecture

**3-Service Architecture:**
```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│    nginx    │────│ voice-notes  │────│   ollama    │
│ (HTTPS/PWA) │    │     API      │    │ (AI Models) │
│   Port 443  │    │  (Backend)   │    │ (Internal)  │
└─────────────┘    └──────────────┘    └─────────────┘
```

- **nginx**: Handles HTTPS, PWA assets, rate limiting
- **voice-notes-api**: FastAPI backend with Whisper transcription
- **ollama**: Local LLM for summarization (llama2:7b default)

## 🛠️ Development

### Commands
```bash
# View all service logs
docker-compose logs -f

# Restart specific service
docker-compose restart voice-notes-api

# Run tests
pytest tests/ -v --cov=app

# Code quality
black app tests && mypy app
```

### Project Structure
```
dialtone/
├── app/                    # FastAPI application
│   ├── api/               # REST endpoints (audio, sessions, vault)
│   ├── core/              # Settings, middleware, exceptions
│   ├── services/          # Business logic (AI, storage, etc.)
│   ├── static/            # PWA frontend (HTML/CSS/JS)
│   └── main.py           # Application entry point
├── nginx/                 # HTTPS reverse proxy config
├── scripts/              # Setup and maintenance scripts
├── tests/                # Comprehensive test suite
└── docs/                 # Additional documentation
```

## 🔧 Configuration

### Environment Variables
Key settings in `.env`:
```bash
# Paths
OBSIDIAN_VAULT_PATH=/path/to/vault     # Required - your Obsidian vault

# AI Models  
WHISPER_MODEL_SIZE=base                # tiny|base|small|medium|large
OLLAMA_MODEL=llama2:7b                 # AI model for summarization

# Processing Limits
MAX_UPLOAD_SIZE=52428800               # 50MB file size limit
PROCESSING_TIMEOUT=35                  # 35 second timeout
MAX_CONCURRENT_REQUESTS=3              # Rate limiting

# HTTPS (auto-configured by setup script)
HTTPS_ENABLED=true
DOMAIN_NAME=localhost
```

### Production Setup
For production with real SSL certificates:
```bash
# Interactive production wizard
./scripts/setup.sh --production
```

See [Production Setup Guide](docs/deployment/production-setup.md) for details.

## 🩺 Troubleshooting

### Common Issues

**"Certificate not trusted" warning:**
- Normal for development with self-signed certificates
- Click "Advanced" → "Proceed to localhost"
- For production, use `--production` flag for real SSL

**PWA won't install:**
- Ensure you're using HTTPS (not HTTP)  
- Try different browser (Chrome/Safari recommended)
- Check browser developer tools for errors

**AI processing slow/failing:**
```bash
# Check service health
docker-compose ps
curl https://localhost/health

# View AI service logs
docker-compose logs ollama
docker-compose logs voice-notes-api
```

**Out of memory errors:**
```bash
# Adjust resource limits in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 8G  # Increase for larger models
```

**Obsidian vault access issues:**
```bash
# Check vault permissions
ls -la /path/to/your/vault
touch /path/to/your/vault/test.md  # Test write access
```

### Performance Optimization

**For lower-resource systems:**
```bash
# Use smaller AI models in .env
WHISPER_MODEL_SIZE=tiny     # Faster, less accurate
OLLAMA_MODEL=llama2:7b      # Smaller than 13b version
```

**For higher accuracy:**
```bash
WHISPER_MODEL_SIZE=medium   # Better transcription
OLLAMA_MODEL=llama2:13b     # Better summaries (needs more RAM)
```

## 📊 System Requirements

### Minimum (Basic Usage)
- **RAM**: 8GB
- **Storage**: 10GB free
- **CPU**: 2 cores
- **Network**: Internet for initial setup

### Recommended (Smooth Experience)  
- **RAM**: 16GB+
- **Storage**: 20GB+ (SSD preferred)
- **CPU**: 4+ cores
- **Network**: Local network access

### Performance Targets ✅
- **Setup time**: < 10 minutes (automated)
- **Processing**: < 35s for 5-minute audio
- **Transcription accuracy**: > 95% (with base model)
- **Uptime**: > 99.9% (with proper hosting)

## 🎯 Completed Features

✅ **Complete PWA Frontend** - Mobile app experience with offline support  
✅ **Local AI Processing** - Whisper + Ollama integration  
✅ **Audio Upload & Processing** - Multi-format support with validation  
✅ **Smart Note Generation** - Transcripts, summaries, keywords  
✅ **Session Management** - Drafts, auto-save, recovery  
✅ **Obsidian Integration** - Direct vault writing  
✅ **HTTPS/SSL Setup** - Automated certificate generation  
✅ **Docker Environment** - Multi-service orchestration  
✅ **Rate Limiting** - API protection and performance  
✅ **Health Monitoring** - Service status and diagnostics  
✅ **Comprehensive Testing** - Unit, integration, performance tests  

## 📚 Additional Documentation

- **[Production Setup](docs/deployment/production-setup.md)** - SSL, domain setup, monitoring  
- **[PWA Installation Guide](docs/pwa-installation.md)** - Device-specific instructions
- **[API Documentation](docs/api/)** - REST endpoints and examples  
- **[Development Guide](CLAUDE.md)** - Architecture and coding standards  
- **[Ollama Integration](docs/ollama-integration.md)** - AI model configuration  

## 🤝 Support

**Need help?**
1. Check logs: `docker-compose logs -f`
2. Review documentation in `docs/`
3. Check GitHub issues for known problems

**Contributing:**
See [CLAUDE.md](CLAUDE.md) for development guidelines and architecture details.