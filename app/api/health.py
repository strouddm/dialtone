"""Health check endpoint."""

from typing import Dict

from fastapi import APIRouter, status

from app.core.health import HealthResponse, HealthService
from app.core.health.models import HealthStatus
from app.core.settings import settings

router = APIRouter(tags=["health"])
health_service = HealthService()


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    response_model=HealthResponse,
    summary="Health check",
    description="Check if the API is running and healthy with comprehensive system monitoring",
    response_description="Complete health status with system metrics and service dependencies",
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {
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
                            "load_average": [0.5, 0.8, 1.2],
                        },
                        "services": {
                            "whisper": "healthy",
                            "vault": "healthy",
                            "storage": "healthy",
                        },
                        "checks": [
                            {
                                "name": "vault_access",
                                "status": "healthy",
                                "message": "Obsidian vault accessible",
                            },
                            {
                                "name": "whisper_model",
                                "status": "healthy",
                                "message": "Whisper model loaded and ready",
                            },
                        ],
                        "features": {
                            "audio_upload": True,
                            "transcription": True,
                            "vault_integration": True,
                        },
                        "app_name": "Dialtone Voice Notes API",
                    }
                }
            },
        },
        503: {
            "description": "Service is unhealthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "timestamp": "2024-11-30T14:30:52.123456",
                        "version": "0.1.0",
                        "uptime_seconds": 120.5,
                        "system": {
                            "cpu_percent": 95.2,
                            "memory_percent": 98.1,
                            "memory_used_gb": 4.9,
                            "memory_total_gb": 5.0,
                            "disk_percent": 95.8,
                            "load_average": [8.5, 9.2, 10.1],
                        },
                        "services": {
                            "whisper": "unhealthy",
                            "vault": "healthy",
                            "storage": "degraded",
                        },
                        "checks": [
                            {
                                "name": "vault_access",
                                "status": "healthy",
                                "message": "Obsidian vault accessible",
                            },
                            {
                                "name": "whisper_model",
                                "status": "unhealthy",
                                "message": "Whisper model failed to load",
                            },
                        ],
                        "features": {
                            "audio_upload": True,
                            "transcription": False,
                            "vault_integration": True,
                        },
                        "app_name": "Dialtone Voice Notes API",
                    }
                }
            },
        },
    },
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
    response_description="Readiness status for all critical services",
    responses={
        200: {
            "description": "All services are ready",
            "content": {
                "application/json": {
                    "example": {
                        "ready": True,
                        "vault_accessible": True,
                        "whisper_loaded": True,
                        "ollama_connected": True,
                    }
                }
            },
        },
        503: {
            "description": "One or more services are not ready",
            "content": {
                "application/json": {
                    "example": {
                        "ready": False,
                        "vault_accessible": True,
                        "whisper_loaded": False,
                        "ollama_connected": False,
                    }
                }
            },
        },
    },
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
