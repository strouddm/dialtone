"""Main FastAPI application."""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api import audio, health, vault
from app.config import setup_logging
from app.core.exceptions import VoiceNotesError
from app.core.handlers import (
    general_exception_handler,
    http_exception_handler,
    validation_error_handler,
    voice_notes_error_handler,
)
from app.core.middleware import LoggingMiddleware, RequestIDMiddleware
from app.core.settings import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application startup and shutdown."""
    # Startup
    logger.info(
        "Starting Dialtone API",
        extra={
            "version": __version__,
            "settings": {
                "vault_path": str(settings.obsidian_vault_path),
                "max_upload_size": settings.max_upload_size,
                "processing_timeout": settings.processing_timeout,
                "ollama_enabled": settings.ollama_enabled,
            },
        },
    )

    # Initialize Ollama service if enabled
    if settings.ollama_enabled:
        try:
            from app.services.ollama import ollama_service

            logger.info("Initializing Ollama service")
            # Check if service is accessible
            if await ollama_service.health_check():
                logger.info("Ollama service is healthy")
                # Try to ensure model is loaded (non-blocking)
                try:
                    await ollama_service.ensure_model_loaded()
                    logger.info(
                        f"Ollama model {settings.ollama_model} loaded successfully"
                    )
                except Exception as e:
                    logger.warning(f"Could not pre-load Ollama model: {e}")
            else:
                logger.warning(
                    "Ollama service is not accessible - will retry on first request"
                )

        except Exception as e:
            logger.error(f"Failed to initialize Ollama service: {e}")

    yield

    # Shutdown
    logger.info("Shutting down Dialtone API")

    # Clean up Ollama service
    if settings.ollama_enabled:
        try:
            from app.services.ollama import ollama_service

            await ollama_service.close()
            logger.info("Ollama service connection closed")
        except Exception as e:
            logger.warning(f"Error closing Ollama service: {e}")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    # Setup logging first
    setup_logging()

    # Create FastAPI app
    app = FastAPI(
        title=settings.app_name,
        description="Self-hosted voice-to-Obsidian system with local AI processing. "
        "Record audio on any device, process locally with Whisper AI, "
        "and save organized notes directly to your Obsidian vault.",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        contact={
            "name": "Dialtone API Support",
            "url": "https://github.com/strouddm/dialtone",
        },
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
        servers=[
            {"url": "http://localhost:8000", "description": "Development server"},
            {
                "url": "https://your-domain.com",
                "description": "Production server (configure with your domain)",
            },
        ],
        openapi_tags=[
            {
                "name": "health",
                "description": "Health check and system monitoring endpoints",
            },
            {
                "name": "audio",
                "description": "Audio upload and transcription endpoints",
            },
            {
                "name": "vault",
                "description": "Obsidian vault integration endpoints",
            },
        ],
    )

    # Add CORS middleware for PWA frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure properly for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add custom middleware
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(LoggingMiddleware)

    # Register exception handlers
    app.add_exception_handler(
        VoiceNotesError, voice_notes_error_handler  # type: ignore[arg-type]
    )
    app.add_exception_handler(
        RequestValidationError, validation_error_handler  # type: ignore[arg-type]
    )
    app.add_exception_handler(
        StarletteHTTPException, http_exception_handler  # type: ignore[arg-type]
    )
    app.add_exception_handler(Exception, general_exception_handler)

    # Root endpoint
    @app.get(
        "/",
        response_model=Dict[str, Any],
        summary="API Information",
        description="Get basic information about the Dialtone API, "
        "including version and available endpoints",
        response_description="API metadata and navigation links",
        responses={
            200: {
                "description": "API information retrieved successfully",
                "content": {
                    "application/json": {
                        "example": {
                            "name": "Dialtone Voice Notes API",
                            "version": "0.1.0",
                            "description": "Voice to Obsidian API",
                            "docs": "/docs",
                            "health": "/health",
                            "endpoints": {
                                "upload": "/api/v1/audio/upload",
                                "transcribe": "/api/v1/audio/transcribe",
                            },
                        }
                    }
                },
            }
        },
    )
    async def root():
        """
        Get API information and navigation links.

        This endpoint provides basic metadata about the API including:
        - Service name and version
        - Available documentation links
        - Key endpoint paths
        - Health check location
        """
        return {
            "name": settings.app_name,
            "version": __version__,
            "description": "Voice to Obsidian API",
            "docs": "/docs",
            "health": "/health",
            "endpoints": {
                "upload": "/api/v1/audio/upload",
                "transcribe": "/api/v1/audio/transcribe",
                "vault_save": "/api/v1/vault/save",
            },
        }

    # Include routers
    app.include_router(health.router)
    app.include_router(audio.router, prefix="/api/v1")
    app.include_router(vault.router, prefix="/api/v1")

    return app


# Create app instance
app = create_app()
