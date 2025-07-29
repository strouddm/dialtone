"""Health check endpoint."""

import time
from typing import Dict, Any

from fastapi import APIRouter, status

from app import __version__
from app.core.settings import settings


router = APIRouter(tags=["health"])


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    response_model=Dict[str, Any],
    summary="Health check",
    description="Check if the API is running and healthy",
)
async def health_check() -> Dict[str, Any]:
    """Return health status and version information."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": __version__,
        "app_name": settings.app_name,
        "features": {
            "audio_upload": True,   # Completed in issue #2
            "transcription": False,  # Will be True after issue #3
            "summarization": False,  # Will be True after issue #9
        },
    }


@router.get(
    "/ready",
    status_code=status.HTTP_200_OK,
    response_model=Dict[str, bool],
    summary="Readiness check",
    description="Check if the API is ready to handle requests",
)
async def readiness_check() -> Dict[str, bool]:
    """Check if all services are ready."""
    # Check vault path is accessible
    vault_ready = settings.obsidian_vault_path.exists() and settings.obsidian_vault_path.is_dir()
    
    # Future checks will include:
    # - Whisper model loaded
    # - Ollama connection
    # - Database connection
    
    all_ready = vault_ready
    
    return {
        "ready": all_ready,
        "vault_accessible": vault_ready,
        "whisper_loaded": False,  # Future
        "ollama_connected": False,  # Future
    }