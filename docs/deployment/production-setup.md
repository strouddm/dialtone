# Production Setup Guide

This guide walks you through setting up Dialtone for production use with the enhanced setup script.

## Prerequisites

### System Requirements

**Minimum Hardware:**
- 8GB RAM (for AI models)
- 10GB free disk space
- 2 CPU cores
- Internet connection for initial setup

**Recommended Hardware:**
- 16GB RAM or more
- 20GB+ free disk space  
- 4+ CPU cores
- SSD storage for better performance

**Software Requirements:**
- Docker 20.10+ with Docker Compose
- Linux/macOS operating system
- Domain name (optional, for SSL)

### Before You Start

1. **Prepare your Obsidian vault**: Ensure your Obsidian vault directory exists and is accessible
2. **Domain setup** (if using SSL): Point your domain to your server's IP address
3. **Firewall configuration**: Ensure ports 80 and 443 are open for web access

## Quick Setup

### One-Command Production Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/dialtone.git
cd dialtone

# Run production setup with interactive wizard
./scripts/setup.sh --production
```

The setup wizard will guide you through:
1. Obsidian vault path configuration
2. SSL certificate setup (optional)
3. AI model selection
4. Performance optimization
5. Security settings

### Setup Wizard Options

#### Obsidian Vault Configuration
- **Path**: Full path to your Obsidian vault directory
- **Permissions**: Script will verify write access
- **Test**: Creates a test file to ensure connectivity

#### SSL Certificate Setup
- **Enable HTTPS**: Recommended for production use
- **Domain name**: Your domain pointing to the server
- **Email**: For Let's Encrypt certificate notifications
- **Auto-renewal**: Configures automatic certificate renewal

#### AI Model Selection

**Whisper Models:**
- `tiny` - Fastest, lowest accuracy (~39MB)
- `base` - Good balance (~74MB) **[Recommended]**
- `small` - Better accuracy (~244MB)
- `medium` - High accuracy (~769MB)
- `large` - Highest accuracy (~1550MB)

**Ollama Models:**
- `llama2:7b` - Good balance (~3.8GB) **[Recommended]**
- `llama2:13b` - Better quality (~7.3GB)
- `mistral:7b` - Fast and efficient (~4.1GB)
- `codellama:7b` - Code-focused (~3.8GB)

#### Performance Settings
- **API Port**: Default 8000, or choose available port
- **Upload Size**: 25MB to 200MB (default: 50MB)
- **Processing Timeout**: 10-300 seconds (default: 35s)

## Manual Configuration

If you prefer manual configuration, you can customize the setup:

### 1. Environment Configuration

Create `.env.prod` with your settings:

```bash
# Copy template and customize
cp scripts/templates/.env.prod.template .env.prod

# Edit configuration
nano .env.prod
```

Key settings to modify:
```bash
OBSIDIAN_VAULT_PATH=/path/to/your/vault
DOMAIN=your-domain.com
EMAIL=your-email@domain.com
ENABLE_SSL=true
WHISPER_MODEL_SIZE=base
OLLAMA_MODEL=llama2:7b
```

### 2. Docker Configuration

```bash
# Copy production Docker Compose
cp scripts/templates/docker-compose.prod.yml docker-compose.yml

# Generate Nginx configuration
# (This is done automatically by the setup script)
```

### 3. SSL Setup (Optional)

If enabling SSL, the setup script will:
1. Configure Nginx for SSL termination
2. Request Let's Encrypt certificates
3. Set up automatic renewal

## Post-Setup Verification

### Health Checks

```bash
# Check service status
docker-compose ps

# Verify API health
curl https://your-domain.com/health
# or for HTTP: curl http://localhost:8000/health

# Check individual services
curl http://localhost:11434/api/tags  # Ollama
```

### Test Audio Processing

1. Open your domain in a browser
2. Record a short audio clip
3. Verify transcription and summarization
4. Check that the note appears in your Obsidian vault

### Monitor Logs

```bash
# View all service logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f voice-notes-api
docker-compose logs -f ollama
docker-compose logs -f nginx
```

## Production Management

### Daily Operations

```bash
# Check system health
./monitor.sh

# View system status
docker-compose ps
docker stats
```

### Maintenance

```bash
# Run maintenance tasks
./maintenance.sh

# Update services
docker-compose pull
docker-compose up -d

# Backup configuration
tar -czf dialtone-backup-$(date +%Y%m%d).tar.gz .env.prod docker-compose.yml nginx.conf
```

### SSL Certificate Management

```bash
# Check certificate status
docker-compose exec nginx nginx -T

# Manual certificate renewal
./renew-certs.sh

# View certificate expiration
openssl x509 -in /path/to/cert.pem -text -noout | grep "Not After"
```

### Troubleshooting

#### Service Issues

```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart voice-notes-api

# View detailed logs
docker-compose logs --tail=100 voice-notes-api
```

#### SSL Issues

```bash
# Test SSL configuration
docker-compose exec nginx nginx -t

# Regenerate certificates
docker-compose --profile ssl-setup run --rm certbot renew --force-renewal

# Fall back to HTTP
sed -i 's/ENABLE_SSL=true/ENABLE_SSL=false/' .env.prod
docker-compose restart
```

#### Performance Issues

```bash
# Check resource usage
docker stats

# Check system resources
free -h
df -h

# Adjust model sizes in .env.prod if needed
WHISPER_MODEL_SIZE=tiny  # Use smaller model
```

#### Vault Access Issues

```bash
# Check vault permissions
ls -la /path/to/vault
touch /path/to/vault/test-file  # Test write access

# Fix permissions if needed
chmod 755 /path/to/vault
chown user:group /path/to/vault
```

## Security Considerations

### Network Security
- Use HTTPS in production (enabled by default)
- Configure firewall to allow only necessary ports
- Regular security updates for Docker and host system

### Data Protection
- Vault data remains local (no cloud processing)
- Audio files are processed locally and can be deleted
- Consider encrypted storage for sensitive vaults

### Access Control
- API rate limiting enabled by default
- Consider adding authentication for public deployments
- Monitor access logs regularly

## Performance Optimization

### Resource Allocation
- Adjust Docker resource limits in `docker-compose.yml`
- Monitor memory usage with larger models
- Use SSD storage for better I/O performance

### Model Selection
- Start with `base` Whisper model for balanced performance
- Upgrade to larger models if accuracy is insufficient
- Consider smaller models for resource-constrained environments

### Scaling Considerations
- Single-node deployment suitable for personal/small team use
- For larger deployments, consider:
  - Load balancing with multiple API instances
  - Separate Ollama service on dedicated hardware
  - Redis for session management

## Backup and Recovery

### Configuration Backup
```bash
# Backup configuration files
tar -czf config-backup.tar.gz .env.prod docker-compose.yml nginx.conf

# Backup Docker volumes
docker run --rm -v dialtone_whisper_cache:/data -v $(pwd):/backup alpine tar czf /backup/whisper-cache.tar.gz -C /data .
```

### Disaster Recovery
1. Keep configuration backups in secure location
2. Document custom configurations
3. Test restore procedures regularly
4. Consider automated backup solutions

## Support and Updates

### Getting Help
- Check logs first: `docker-compose logs`
- Review this documentation
- Check GitHub issues for known problems

### Updating Dialtone
```bash
# Pull latest code
git pull origin main

# Update Docker images
docker-compose pull

# Restart with new images
docker-compose up -d

# Run any new migrations
# (Currently none, but check release notes)
```

### Version Management
- Keep track of your Dialtone version
- Review release notes before updating
- Test updates in development environment first