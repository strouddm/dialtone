"""Main FastAPI application."""

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api import audio, health
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
            },
        },
    )

    yield

    # Shutdown
    logger.info("Shutting down Dialtone API")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    # Setup logging first
    setup_logging()

    # Create FastAPI app
    app = FastAPI(
        title=settings.app_name,
        description="Self-hosted voice-to-Obsidian system with local AI processing",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
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
    app.add_exception_handler(VoiceNotesError, voice_notes_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    # Root endpoint
    @app.get("/", response_model=Dict[str, Any])
    async def root():
        """Root endpoint with API information."""
        return {
            "name": settings.app_name,
            "version": __version__,
            "description": "Voice to Obsidian API",
            "docs": "/docs",
            "health": "/health",
        }

    # Include routers
    app.include_router(health.router)
    app.include_router(audio.router)

    return app


# Create app instance
app = create_app()
