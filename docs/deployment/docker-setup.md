# Docker Deployment Guide

Get Dialtone running locally in minutes with Docker Compose.

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 6+ CPU cores, 16GB RAM
- ~5GB disk space for models

## Quick Setup

### 1. Clone and Configure

```bash
# Clone repository
git clone https://github.com/strouddm/dialtone.git
cd dialtone

# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

### 2. Essential Configuration

Edit `.env` with your settings:

```bash
# Required: Your Obsidian vault path
OBSIDIAN_VAULT_PATH=/path/to/your/obsidian/vault

# Optional: Customize processing
MAX_UPLOAD_SIZE=52428800  # 50MB in bytes
PROCESSING_TIMEOUT=300    # 5 minutes
WHISPER_MODEL=base        # base, small, medium, large

# Optional: SSL for mobile access
SSL_CERT_PATH=/path/to/cert.pem
SSL_KEY_PATH=/path/to/private.key
```

### 3. Start Services

```bash
# Start all services
docker-compose up -d

# Monitor startup logs
docker-compose logs -f

# Wait for Whisper model download (first run only)
# This may take 5-10 minutes depending on your connection
```

### 4. Verify Installation

```bash
# Check service health
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "version": "0.1.0",
  "services": {
    "whisper": "healthy",
    "vault": "healthy"
  }
}

# Check readiness
curl http://localhost:8000/ready

# Test API documentation
open http://localhost:8000/docs
```

## Production Setup

### HTTPS with Let's Encrypt

For mobile PWA support, HTTPS is required:

```bash
# Install certbot
sudo apt install certbot

# Get SSL certificate
sudo certbot certonly --standalone -d your-domain.com

# Update docker-compose.yml
# Uncomment nginx SSL section and update paths
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OBSIDIAN_VAULT_PATH` | `./vault` | Path to Obsidian vault |
| `MAX_UPLOAD_SIZE` | `52428800` | Max file size (50MB) |
| `PROCESSING_TIMEOUT` | `300` | Processing timeout (5min) |
| `WHISPER_MODEL` | `base` | Whisper model size |
| `LOG_LEVEL` | `INFO` | Logging level |
| `API_HOST` | `0.0.0.0` | API bind address |
| `API_PORT` | `8000` | API port |

### Resource Requirements

| Component | CPU | RAM | Disk |
|-----------|-----|-----|------|
| API Server | 1 core | 1GB | 100MB |
| Whisper Base | 2-4 cores | 2GB | 1GB |
| Nginx | 0.5 core | 100MB | 10MB |
| **Total** | **4-6 cores** | **3-4GB** | **1.2GB** |

**Note**: Large Whisper model requires 8GB+ RAM

## Troubleshooting

### Common Issues

**Service won't start:**
```bash
# Check Docker logs
docker-compose logs api
docker-compose logs nginx

# Check system resources
docker stats
```

**Whisper model download fails:**
```bash
# Check internet connection and disk space
df -h
docker-compose exec api python -c "import whisper; whisper.load_model('base')"
```

**Upload fails:**
```bash
# Check file permissions
ls -la /path/to/vault
docker-compose exec api ls -la /app/uploads
```

**Mobile can't connect:**
```bash
# Verify HTTPS setup
curl -I https://your-domain.com/health
# Check firewall
sudo ufw status
```

### Performance Tuning

**Slow transcription:**
- Use smaller Whisper model (`tiny`, `base`)
- Increase CPU/RAM allocation
- Pre-process audio to 16kHz mono

**High memory usage:**
- Use `base` instead of `large` model
- Set Docker memory limits
- Monitor with `docker stats`

### Backup & Recovery

**Backup configuration:**
```bash
# Backup volumes
docker run --rm -v dialtone_uploads:/data -v $(pwd):/backup ubuntu tar czf /backup/uploads.tar.gz /data

# Backup environment
cp .env .env.backup
```

**Update procedure:**
```bash
# Pull latest changes
git pull origin main

# Rebuild containers
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

**Still having issues?** Check our [troubleshooting guide](troubleshooting.md) or [open an issue](https://github.com/strouddm/dialtone/issues).