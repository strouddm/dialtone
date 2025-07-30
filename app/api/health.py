"""Health check endpoint."""

import time
from typing import Dict, Any

from fastapi import APIRouter, status

from app import __version__
from app.core.health import HealthResponse, HealthService
from app.core.settings import settings


router = APIRouter(tags=["health"])
health_service = HealthService()


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    response_model=HealthResponse,
    summary="Health check",
    description="Check if the API is running and healthy with comprehensive system monitoring",
)
async def health_check() -> HealthResponse:
    """Return comprehensive health status with system monitoring."""
    return await health_service.get_health_status()


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
    vault_ready = (
        settings.obsidian_vault_path.exists() and settings.obsidian_vault_path.is_dir()
    )

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
