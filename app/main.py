"""Main FastAPI application."""

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api import audio, health
from app.config import setup_logging
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

    # Add request ID middleware
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        """Add request ID for tracking."""
        request_id = f"{time.time():.6f}"
        request.state.request_id = request_id

        # Log request
        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
            },
        )

        # Process request
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time

        # Log response
        logger.info(
            "Request completed",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),
            },
        )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        return response

    # Exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle uncaught exceptions."""
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            "Unhandled exception",
            extra={
                "request_id": request_id,
                "error": str(exc),
                "type": type(exc).__name__,
            },
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "request_id": request_id,
            },
        )

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
