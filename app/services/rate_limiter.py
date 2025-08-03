"""Rate limiting service using token bucket algorithm."""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from app.core.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """Token bucket for rate limiting with refill mechanism."""

    capacity: int
    tokens: float
    refill_rate: float  # tokens per second
    last_refill: float

    def __post_init__(self) -> None:
        """Initialize bucket with full capacity."""
        if self.tokens > self.capacity:
            self.tokens = float(self.capacity)

    def consume(self, tokens: int = 1) -> bool:
        """
        Attempt to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if insufficient tokens
        """
        current_time = time.time()
        self._refill(current_time)

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _refill(self, current_time: float) -> None:
        """Refill the bucket based on elapsed time and refill rate."""
        time_elapsed = current_time - self.last_refill
        tokens_to_add = time_elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = current_time

    def get_wait_time(self) -> float:
        """
        Calculate wait time until next token is available.

        Returns:
            Seconds to wait until next token is available
        """
        if self.tokens >= 1.0:
            return 0.0
        return (1.0 - self.tokens) / self.refill_rate

    def get_reset_time(self) -> float:
        """
        Calculate time when bucket will be fully refilled.

        Returns:
            Unix timestamp when bucket will be full
        """
        if self.tokens >= self.capacity:
            return time.time()
        tokens_needed = self.capacity - self.tokens
        seconds_to_full = tokens_needed / self.refill_rate
        return time.time() + seconds_to_full


@dataclass
class RateLimitInfo:
    """Rate limit information for response headers."""

    limit: int
    remaining: int
    reset_time: float
    retry_after: Optional[float] = None


class RateLimiter:
    """Rate limiting service with per-client token buckets."""

    def __init__(self) -> None:
        """Initialize rate limiter with empty client buckets."""
        self._buckets: Dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._last_cleanup = time.time()

    async def check_rate_limit(
        self, client_id: str, endpoint_type: str = "default"
    ) -> Tuple[bool, RateLimitInfo]:
        """
        Check if request should be allowed based on rate limits.

        Args:
            client_id: Unique identifier for the client
            endpoint_type: Type of endpoint for specific limits

        Returns:
            Tuple of (allowed, rate_limit_info)
        """
        if not settings.rate_limiting_enabled:
            # Rate limiting disabled, allow request with dummy info
            return True, RateLimitInfo(
                limit=1000, remaining=999, reset_time=time.time() + 60
            )

        async with self._lock:
            bucket = await self._get_or_create_bucket(client_id, endpoint_type)
            allowed = bucket.consume(1)

            rate_limit_info = RateLimitInfo(
                limit=bucket.capacity,
                remaining=int(bucket.tokens),
                reset_time=bucket.get_reset_time(),
                retry_after=bucket.get_wait_time() if not allowed else None,
            )

            # Trigger cleanup if needed
            await self._maybe_cleanup()

            logger.debug(
                "Rate limit check",
                extra={
                    "client_id": client_id,
                    "endpoint_type": endpoint_type,
                    "allowed": allowed,
                    "remaining": rate_limit_info.remaining,
                    "bucket_tokens": bucket.tokens,
                },
            )

            return allowed, rate_limit_info

    async def _get_or_create_bucket(
        self, client_id: str, endpoint_type: str
    ) -> TokenBucket:
        """Get existing bucket or create new one for client."""
        bucket_key = f"{client_id}:{endpoint_type}"

        if bucket_key not in self._buckets:
            limit = self._get_limit_for_endpoint(endpoint_type)
            refill_rate = limit / 60.0  # Convert per-minute to per-second

            self._buckets[bucket_key] = TokenBucket(
                capacity=min(limit, settings.rate_limit_burst_size),
                tokens=float(min(limit, settings.rate_limit_burst_size)),
                refill_rate=refill_rate,
                last_refill=time.time(),
            )

            logger.debug(
                "Created new rate limit bucket",
                extra={
                    "client_id": client_id,
                    "endpoint_type": endpoint_type,
                    "bucket_key": bucket_key,
                    "limit": limit,
                    "refill_rate": refill_rate,
                },
            )

        return self._buckets[bucket_key]

    def _get_limit_for_endpoint(self, endpoint_type: str) -> int:
        """Get rate limit for specific endpoint type."""
        endpoint_limits = {
            "upload": settings.rate_limit_upload_per_minute,
            "transcribe": settings.rate_limit_transcribe_per_minute,
            "health": settings.rate_limit_health_per_minute,
        }
        return endpoint_limits.get(endpoint_type, settings.rate_limit_requests_per_minute)

    async def _maybe_cleanup(self) -> None:
        """Trigger cleanup if enough time has passed."""
        current_time = time.time()
        if (
            current_time - self._last_cleanup
            > settings.rate_limit_cleanup_interval
        ):
            await self._cleanup_expired_buckets()
            self._last_cleanup = current_time

    async def _cleanup_expired_buckets(self) -> None:
        """Remove expired buckets to prevent memory leaks."""
        current_time = time.time()
        expired_keys = []

        for bucket_key, bucket in self._buckets.items():
            # Consider bucket expired if it hasn't been used for cleanup interval
            time_since_refill = current_time - bucket.last_refill
            if time_since_refill > settings.rate_limit_cleanup_interval:
                expired_keys.append(bucket_key)

        for key in expired_keys:
            del self._buckets[key]

        if expired_keys:
            logger.info(
                "Cleaned up expired rate limit buckets",
                extra={
                    "expired_count": len(expired_keys),
                    "remaining_buckets": len(self._buckets),
                },
            )

    def get_client_identifier(self, client_ip: str, user_agent: str) -> str:
        """
        Generate unique client identifier from IP and User-Agent.

        Args:
            client_ip: Client IP address
            user_agent: Client User-Agent header

        Returns:
            Unique client identifier string
        """
        # Hash user agent to avoid storing full strings
        user_agent_hash = hashlib.sha256(user_agent.encode()).hexdigest()[:8]
        return f"{client_ip}:{user_agent_hash}"

    async def get_stats(self) -> Dict[str, int]:
        """
        Get rate limiter statistics.

        Returns:
            Dictionary with rate limiter stats
        """
        async with self._lock:
            active_buckets = len(self._buckets)
            total_tokens = sum(bucket.tokens for bucket in self._buckets.values())
            
            return {
                "active_buckets": active_buckets,
                "total_remaining_tokens": int(total_tokens),
                "cleanup_interval": settings.rate_limit_cleanup_interval,
                "rate_limiting_enabled": settings.rate_limiting_enabled,
            }

    async def reset_client(self, client_id: str, endpoint_type: str = "default") -> None:
        """
        Reset rate limit for a specific client and endpoint.

        Args:
            client_id: Client identifier to reset
            endpoint_type: Endpoint type to reset
        """
        async with self._lock:
            bucket_key = f"{client_id}:{endpoint_type}"
            if bucket_key in self._buckets:
                del self._buckets[bucket_key]
                logger.info(
                    "Reset rate limit for client",
                    extra={
                        "client_id": client_id,
                        "endpoint_type": endpoint_type,
                    },
                )


# Global rate limiter instance
rate_limiter = RateLimiter()