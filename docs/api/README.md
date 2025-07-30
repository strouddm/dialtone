# API Reference

Complete reference for the Dialtone Voice Notes API.

## Base URL

- **Development**: `http://localhost:8000`
- **Production**: `https://your-domain.com`

## Authentication

Currently no authentication required. All endpoints are publicly accessible.

⚠️ **Security Note**: In production, consider adding API keys or IP restrictions.

## Rate Limiting

- **Upload**: 3 concurrent requests
- **Transcription**: 1 concurrent request per upload
- **Health**: Unlimited

## Content Types

- **Request**: `multipart/form-data` (file uploads), `application/json` (data)
- **Response**: `application/json`

## Error Format

All errors follow this structure:

```json
{
  "error": "Human readable error message",
  "error_code": "MACHINE_READABLE_CODE",
  "request_id": "req_123456789",
  "details": {
    "additional": "context"
  }
}
```

## Endpoints

### 🏠 Root & Info

#### GET `/`
Get API information and navigation links.

**Response:**
```json
{
  "name": "Dialtone Voice Notes API",
  "version": "0.1.0",
  "description": "Voice to Obsidian API",
  "docs": "/docs",
  "health": "/health",
  "endpoints": {
    "upload": "/api/v1/audio/upload",
    "transcribe": "/api/v1/audio/transcribe"
  }
}
```

### 💚 Health & Monitoring

#### GET `/health`
Comprehensive health check with system metrics.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-11-30T14:30:52.123456",
  "version": "0.1.0",
  "uptime_seconds": 3600.5,
  "system": {
    "cpu_percent": 15.2,
    "memory_percent": 45.8,
    "memory_used_gb": 2.3,
    "memory_total_gb": 5.0,
    "disk_percent": 68.4,
    "load_average": [0.5, 0.8, 1.2]
  },
  "services": {
    "whisper": "healthy",
    "vault": "healthy",
    "storage": "healthy"
  }
}
```

#### GET `/ready`
Quick readiness check for critical services.

**Response:**
```json
{
  "ready": true,
  "vault_accessible": true,
  "whisper_loaded": true,
  "ollama_connected": false
}
```

### 🎵 Audio Processing

#### POST `/api/v1/audio/upload`
Upload an audio file for processing.

**Request:**
- **Content-Type**: `multipart/form-data`
- **Body**: Form field `file` with audio file

**Supported Formats:**
- WebM (`audio/webm`)
- M4A (`audio/mp4`) 
- MP3 (`audio/mpeg`)
- **Max Size**: 50MB

**Response (200):**
```json
{
  "upload_id": "upload_20241130_143052_abc123",
  "filename": "voice_note_20241130_143052.webm",
  "file_size": 1024576,
  "mime_type": "audio/webm",
  "status": "uploaded",
  "created_at": "2024-11-30T14:30:52.123456"
}
```

#### POST `/api/v1/audio/transcribe`
Transcribe an uploaded audio file.

**Request:**
```json
{
  "upload_id": "upload_20241130_143052_abc123",
  "language": "en"  // optional
}
```

**Response (200):**
```json
{
  "upload_id": "upload_20241130_143052_abc123",
  "transcription": {
    "text": "This is a test transcription of my voice note.",
    "language": "en",
    "confidence": 0.95,
    "duration_seconds": 12.5
  },
  "processing_time_seconds": 2.8,
  "status": "completed"
}
```

## Code Examples

### cURL

```bash
# Upload audio file
curl -X POST http://localhost:8000/api/v1/audio/upload \\
  -F "file=@recording.webm"

# Transcribe upload
curl -X POST http://localhost:8000/api/v1/audio/transcribe \\
  -H "Content-Type: application/json" \\
  -d '{"upload_id": "upload_20241130_143052_abc123"}'
```

### JavaScript (Fetch)

```javascript
// Upload audio file
const uploadAudio = async (audioFile) => {
  const formData = new FormData();
  formData.append('file', audioFile);
  
  const response = await fetch('/api/v1/audio/upload', {
    method: 'POST',
    body: formData
  });
  
  return await response.json();
};

// Transcribe audio
const transcribeAudio = async (uploadId) => {
  const response = await fetch('/api/v1/audio/transcribe', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      upload_id: uploadId,
      language: 'en'
    })
  });
  
  return await response.json();
};
```

### Python (requests)

```python
import requests

# Upload audio file
def upload_audio(file_path):
    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(
            'http://localhost:8000/api/v1/audio/upload',
            files=files
        )
    return response.json()

# Transcribe audio
def transcribe_audio(upload_id):
    data = {
        'upload_id': upload_id,
        'language': 'en'
    }
    response = requests.post(
        'http://localhost:8000/api/v1/audio/transcribe',
        json=data
    )
    return response.json()
```

## Error Codes

| Code | HTTP | Description |
|------|------|-------------|
| `MISSING_FILE` | 400 | No file provided in upload |
| `INVALID_FORMAT` | 400 | Unsupported file format |
| `FILE_TOO_LARGE` | 413 | File exceeds 50MB limit |
| `UPLOAD_NOT_FOUND` | 404 | Invalid upload ID |
| `CONVERSION_ERROR` | 400 | Audio format conversion failed |
| `TRANSCRIPTION_ERROR` | 500 | Whisper processing failed |
| `TRANSCRIPTION_TIMEOUT` | 408 | Processing exceeded timeout |
| `SERVICE_UNAVAILABLE` | 503 | Whisper service down |

## Interactive Documentation

Visit `/docs` when the API is running for interactive Swagger UI documentation where you can:

- Test endpoints directly
- See request/response schemas
- Download OpenAPI spec
- Try different parameters

---

**Questions?** Check our [deployment guide](../deployment/docker-setup.md) or [open an issue](https://github.com/strouddm/dialtone/issues).