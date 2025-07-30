"""Middleware for the application."""
import time
import uuid
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add a unique request ID to each request."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process the request and add request ID."""
        # Generate unique request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        # Process request and add ID to response
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log request/response information."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Log request details and response time."""
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate processing time
        process_time = (time.time() - start_time) * 1000  # Convert to ms

        # Add processing time header
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"

        # Log request details
        import logging

        logger = logging.getLogger(__name__)

        logger.info(
            "Request completed",
            extra={
                "request_id": getattr(request.state, "request_id", None),
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "process_time_ms": process_time,
            },
        )

        return response
