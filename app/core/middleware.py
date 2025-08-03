"""Middleware for the application."""

import time
import uuid
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import RateLimitError


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


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using token bucket algorithm."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Check rate limits before processing request."""
        from app.services.rate_limiter import rate_limiter

        # Extract client information
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent")
        endpoint_path = request.url.path

        # Check rate limit
        allowed, retry_after, headers = await rate_limiter.check_rate_limit(
            ip=client_ip, endpoint_path=endpoint_path, user_agent=user_agent
        )

        if not allowed:
            # Rate limit exceeded - raise exception with detailed info
            tokens_per_minute, _ = self._get_endpoint_limits(endpoint_path)
            raise RateLimitError(
                retry_after=int(retry_after) + 1,
                limit=tokens_per_minute,
                endpoint=endpoint_path,
            )

        # Process request normally
        response = await call_next(request)

        # Add rate limit headers to response
        for header_name, header_value in headers.items():
            response.headers[header_name] = header_value

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request, considering proxies."""
        # Check for forwarded IP from reverse proxy
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()

        # Check for real IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # Fall back to direct client IP
        if request.client and hasattr(request.client, "host") and request.client.host:
            return request.client.host

        # Default fallback
        return "unknown"

    def _get_endpoint_limits(self, endpoint_path: str) -> tuple[int, int]:
        """Get rate limits for specific endpoint."""
        from app.core.settings import settings

        # Map endpoint patterns to specific limits
        if "/upload" in endpoint_path:
            return settings.rate_limit_upload_per_minute, settings.rate_limit_burst_size
        elif "/transcribe" in endpoint_path:
            return (
                settings.rate_limit_transcribe_per_minute,
                settings.rate_limit_burst_size,
            )
        elif "/health" in endpoint_path:
            return settings.rate_limit_health_per_minute, settings.rate_limit_burst_size
        else:
            # Default limits for other endpoints
            return (
                settings.rate_limit_requests_per_minute,
                settings.rate_limit_burst_size,
            )
