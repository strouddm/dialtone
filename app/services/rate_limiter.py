"""Rate limiting service using token bucket algorithm."""

import asyncio
import hashlib
import time
from typing import Dict, Optional, Tuple

from app.core.settings import settings


class TokenBucket:
    """Token bucket implementation for rate limiting."""

    def __init__(self, tokens_per_minute: int, burst_size: int) -> None:
        """Initialize token bucket with rate and burst size."""
        self.tokens_per_minute = tokens_per_minute
        self.burst_size = burst_size
        self.tokens = float(burst_size)  # Start with full bucket
        self.last_update = time.time()
        self._lock = asyncio.Lock()

    async def can_consume(self, tokens: int = 1) -> Tuple[bool, float]:
        """
        Check if tokens can be consumed from bucket.

        Returns:
            Tuple of (can_consume: bool, retry_after: float)
        """
        async with self._lock:
            now = time.time()

            # Add tokens based on time elapsed
            time_elapsed = now - self.last_update
            tokens_to_add = (time_elapsed / 60.0) * self.tokens_per_minute
            self.tokens = min(self.burst_size, self.tokens + tokens_to_add)
            self.last_update = now

            # Check if we can consume the requested tokens
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True, 0.0
            else:
                # Calculate retry after time
                tokens_needed = tokens - self.tokens
                retry_after = (tokens_needed / self.tokens_per_minute) * 60.0
                return False, retry_after

    def is_expired(self, max_idle_time: int = 3600) -> bool:
        """Check if bucket has been idle for too long."""
        return (time.time() - self.last_update) > max_idle_time


class RateLimiterService:
    """Rate limiting service managing multiple token buckets."""

    def __init__(self) -> None:
        """Initialize rate limiter service."""
        self._buckets: Dict[str, TokenBucket] = {}
        self._cleanup_lock = asyncio.Lock()
        self._last_cleanup = time.time()

    def _get_client_id(self, ip: str, user_agent: Optional[str] = None) -> str:
        """Generate unique client identifier."""
        # Combine IP and User-Agent hash for better client identification
        if user_agent:
            ua_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
            return f"{ip}:{ua_hash}"
        return ip

    def _get_endpoint_limits(self, endpoint_path: str) -> Tuple[int, int]:
        """Get rate limits for specific endpoint."""
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

    async def check_rate_limit(
        self, ip: str, endpoint_path: str, user_agent: Optional[str] = None
    ) -> Tuple[bool, float, Dict[str, str]]:
        """
        Check rate limit for client and endpoint.

        Returns:
            Tuple of (allowed: bool, retry_after: float, headers: dict)
        """
        if not settings.rate_limiting_enabled:
            return True, 0.0, {}

        client_id = self._get_client_id(ip, user_agent)
        bucket_key = f"{client_id}:{endpoint_path}"

        # Get or create bucket for this client/endpoint combination
        if bucket_key not in self._buckets:
            tokens_per_minute, burst_size = self._get_endpoint_limits(endpoint_path)
            self._buckets[bucket_key] = TokenBucket(tokens_per_minute, burst_size)

        bucket = self._buckets[bucket_key]
        allowed, retry_after = await bucket.can_consume(1)

        # Get current bucket state for headers
        tokens_per_minute, burst_size = self._get_endpoint_limits(endpoint_path)
        remaining_tokens = int(bucket.tokens)

        # Prepare rate limit headers
        headers = {
            "X-RateLimit-Limit": str(tokens_per_minute),
            "X-RateLimit-Remaining": str(max(0, remaining_tokens)),
            "X-RateLimit-Reset": str(int(bucket.last_update + 60)),
        }

        if not allowed:
            headers["Retry-After"] = str(int(retry_after) + 1)  # Round up

        # Periodic cleanup
        await self._maybe_cleanup()

        return allowed, retry_after, headers

    async def _maybe_cleanup(self) -> None:
        """Clean up expired buckets if cleanup interval has passed."""
        now = time.time()
        if now - self._last_cleanup < settings.rate_limit_cleanup_interval:
            return

        async with self._cleanup_lock:
            # Double-check after acquiring lock
            if now - self._last_cleanup < settings.rate_limit_cleanup_interval:
                return

            expired_keys = [
                key for key, bucket in self._buckets.items() if bucket.is_expired()
            ]

            for key in expired_keys:
                del self._buckets[key]

            self._last_cleanup = now

            # Log cleanup activity
            if expired_keys:
                import logging

                logger = logging.getLogger(__name__)
                logger.debug(
                    f"Rate limiter cleaned up {len(expired_keys)} expired buckets"
                )

    async def get_stats(self) -> Dict[str, any]:
        """Get rate limiter statistics."""
        return {
            "active_buckets": len(self._buckets),
            "last_cleanup": self._last_cleanup,
            "cleanup_interval": settings.rate_limit_cleanup_interval,
            "enabled": settings.rate_limiting_enabled,
        }

    async def reset_client(self, ip: str, user_agent: Optional[str] = None) -> None:
        """Reset rate limits for a specific client (for testing/admin)."""
        client_id = self._get_client_id(ip, user_agent)
        keys_to_remove = [
            key for key in self._buckets.keys() if key.startswith(client_id)
        ]

        for key in keys_to_remove:
            del self._buckets[key]


# Global rate limiter instance
rate_limiter = RateLimiterService()
