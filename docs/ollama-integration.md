# Ollama Integration

This document describes the Ollama container integration for AI summarization capabilities.

## Overview

Ollama provides local AI model hosting for generating summaries and extracting keywords from transcribed audio. This integration ensures all AI processing remains local and private.

## Configuration

### Docker Compose

The Ollama service is configured in `docker-compose.yml`:

```yaml
ollama:
  image: ollama/ollama:latest
  container_name: ollama
  ports:
    - "11434"  # Internal only
  volumes:
    - ./ollama-models:/root/.ollama
  environment:
    - OLLAMA_HOST=0.0.0.0
    - OLLAMA_MODELS=/root/.ollama/models
  deploy:
    resources:
      limits:
        cpus: '3'
        memory: 8G
      reservations:
        cpus: '1'
        memory: 2G
```

### Environment Variables

Configure Ollama service through environment variables:

- `OLLAMA_BASE_URL`: Ollama service URL (default: `http://ollama:11434`)
- `OLLAMA_MODEL`: Model to use for summarization (default: `llama2:7b`)
- `OLLAMA_TIMEOUT`: Request timeout in seconds (default: `30`)
- `OLLAMA_ENABLED`: Enable/disable Ollama service (default: `true`)

## Usage

### Service Integration

The Ollama service is automatically initialized when the FastAPI application starts. It provides:

1. **Health Monitoring**: Integrated with the `/health` endpoint
2. **Model Management**: Automatic model loading and validation
3. **Error Handling**: Graceful fallbacks when service is unavailable

### API Methods

The `OllamaService` class provides:

- `generate_summary(text: str, max_length: int = 200) -> str`: Generate AI summary
- `extract_keywords(text: str, max_keywords: int = 5) -> list[str]`: Extract keywords
- `health_check() -> bool`: Check service availability
- `ensure_model_loaded() -> bool`: Ensure model is ready

## Resource Management

### Memory Allocation
- Maximum: 8GB (50% of total system RAM)
- Reserved: 2GB minimum
- Models require ~4GB storage space

### CPU Allocation
- Maximum: 3 cores
- Reserved: 1 core minimum

### Network Security
- Internal Docker network only
- No external port exposure
- Communication via service name (`ollama:11434`)

## Model Management

### Default Model
- **llama2:7b**: Balanced performance and accuracy
- **Size**: ~3.8GB download
- **Performance**: ~2-5 seconds for summaries

### Alternative Models
- **llama2:13b**: Higher accuracy, more resources
- **mistral:7b**: Alternative model with similar performance
- **codellama:7b**: Specialized for code-related content

### Model Loading
Models are automatically downloaded on first use. Pre-loading occurs during application startup when possible.

## Error Handling

### Service Unavailable
When Ollama is unavailable:
- Health checks report degraded status
- API calls throw `ServiceUnavailableError`
- Graceful fallbacks maintain application functionality

### Retry Logic
- Maximum 3 retry attempts
- Exponential backoff (2^attempt seconds)
- Circuit breaker pattern for reliability

### Resource Exhaustion
- Memory limits enforced via Docker
- Automatic container restart on OOM
- Resource monitoring and alerts

## Monitoring

### Health Checks
- Container health: `/api/tags` endpoint
- Model availability: Model listing API
- Response time: <2 seconds for health checks

### Performance Metrics
- Startup time: <60 seconds
- Model loading: <120 seconds
- Memory usage: <8GB steady state
- API response: <30 seconds for summaries

## Troubleshooting

### Common Issues

1. **Container won't start**
   - Check Docker resources (8GB RAM available)
   - Verify ollama-models directory permissions
   - Check logs: `docker logs ollama`

2. **Model download fails**
   - Verify internet connectivity
   - Check disk space (4GB+ required)
   - Try smaller model: `ollama:mistral`

3. **High memory usage**
   - Verify memory limits in docker-compose.yml
   - Consider smaller model (llama2:7b → codellama:7b)
   - Monitor with `docker stats ollama`

4. **Slow responses**
   - Check CPU allocation (increase cores)
   - Verify model is pre-loaded
   - Monitor system load average

### Debugging Commands

```bash
# Check container status
docker ps | grep ollama

# View logs
docker logs ollama -f

# Check resource usage
docker stats ollama

# Test API directly
curl http://localhost:11434/api/tags

# Check available models
curl http://localhost:11434/api/tags | jq '.models[].name'
```

## Security Considerations

### Network Isolation
- No external network access required after model download
- Internal Docker network communication only
- No sensitive data in environment variables

### Data Privacy
- All processing occurs locally
- No data sent to external services
- Model inference completely offline

### Resource Limits
- Strict memory and CPU limits
- Prevents resource exhaustion attacks
- Graceful degradation on limits

## Performance Optimization

### Model Selection
- Use smallest model meeting accuracy requirements
- Balance between speed and quality
- Consider use case (general vs. specialized)

### Resource Tuning
- Adjust CPU cores based on load
- Increase memory for larger models
- Monitor and optimize based on usage patterns

### Caching
- Models persist across container restarts
- HTTP client connection pooling
- Response caching for repeated requests

---

*This integration enables privacy-first AI summarization as part of the Dialtone voice notes system.*