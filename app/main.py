"""Main FastAPI application."""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api import audio, health, sessions, vault
from app.config import setup_logging
from app.core.exceptions import VoiceNotesError
from app.core.handlers import (
    general_exception_handler,
    http_exception_handler,
    validation_error_handler,
    voice_notes_error_handler,
)
from app.core.middleware import LoggingMiddleware, RateLimitingMiddleware, RequestIDMiddleware
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

    # Start session cleanup task
    try:
        from app.tasks.cleanup import start_cleanup_task

        start_cleanup_task()
        logger.info("Session cleanup task started")
    except Exception as e:
        logger.error(f"Failed to start session cleanup task: {e}")

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
                "name": "sessions",
                "description": "Session management for multi-step workflows",
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

    # Mount static files for the web interface
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    # Add custom middleware (order matters - rate limiting first)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(LoggingMiddleware)
    if settings.rate_limiting_enabled:
        app.add_middleware(RateLimitingMiddleware)

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

    # Root endpoint - serve the recording interface
    @app.get(
        "/",
        response_class=FileResponse,
        summary="Recording Interface",
        description="Serve the HTML recording interface for voice notes",
        response_description="HTML recording interface",
        responses={
            200: {
                "description": "Recording interface served successfully",
                "content": {"text/html": {"example": "<!DOCTYPE html>..."}},
            }
        },
    )
    async def root():
        """
        Serve the main recording interface.

        Returns the HTML interface for recording voice notes directly in the browser.
        This is a mobile-optimized Progressive Web App interface that allows users
        to record audio and upload it for transcription and processing.
        """
        return FileResponse("app/static/index.html")

    # PWA manifest endpoint with correct MIME type
    @app.get("/manifest.json", include_in_schema=False)
    async def get_manifest():
        """Serve PWA manifest with correct MIME type."""
        return FileResponse(
            "app/static/manifest.json", media_type="application/manifest+json"
        )

    # API info endpoint for programmatic access
    @app.get(
        "/api",
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
    async def api_info():
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
                "sessions": "/api/v1/sessions",
                "vault_save": "/api/v1/vault/save",
            },
        }

    # Include routers
    app.include_router(health.router)
    app.include_router(audio.router)
    app.include_router(sessions.router)
    app.include_router(vault.router, prefix="/api/v1")

    return app


# Create app instance
app = create_app()
