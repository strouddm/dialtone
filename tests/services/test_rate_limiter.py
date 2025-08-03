"""Tests for rate limiting service."""

import asyncio
import time
from unittest.mock import patch

import pytest

from app.core.exceptions import RateLimitError
from app.services.rate_limiter import RateLimiterService, TokenBucket


class TestTokenBucket:
    """Test TokenBucket implementation."""

    @pytest.fixture
    def bucket(self):
        """Create a token bucket for testing."""
        return TokenBucket(tokens_per_minute=60, burst_size=10)

    async def test_initial_bucket_full(self, bucket):
        """Test that bucket starts full."""
        can_consume, retry_after = await bucket.can_consume(1)
        assert can_consume is True
        assert retry_after == 0.0

    async def test_consume_tokens(self, bucket):
        """Test consuming tokens from bucket."""
        # Consume all tokens
        for _ in range(10):
            can_consume, retry_after = await bucket.can_consume(1)
            assert can_consume is True
            assert retry_after == 0.0

        # Next request should be denied
        can_consume, retry_after = await bucket.can_consume(1)
        assert can_consume is False
        assert retry_after > 0.0

    async def test_token_refill(self, bucket):
        """Test that tokens are refilled over time."""
        # Consume all tokens
        for _ in range(10):
            await bucket.can_consume(1)

        # Mock time to simulate 1 minute passing
        original_time = time.time()
        with patch('time.time', return_value=original_time + 60):
            can_consume, retry_after = await bucket.can_consume(1)
            assert can_consume is True
            assert retry_after == 0.0

    async def test_partial_refill(self, bucket):
        """Test partial token refill."""
        # Consume all tokens
        for _ in range(10):
            await bucket.can_consume(1)

        # Mock time to simulate 30 seconds passing (half a minute)
        original_time = time.time()
        with patch('time.time', return_value=original_time + 30):
            can_consume, retry_after = await bucket.can_consume(1)
            assert can_consume is True  # Should have ~30 tokens refilled

    async def test_max_tokens_cap(self, bucket):
        """Test that tokens don't exceed burst size."""
        # Wait for refill
        original_time = time.time()
        with patch('time.time', return_value=original_time + 120):  # 2 minutes
            # Should still only have 10 tokens max
            for _ in range(10):
                can_consume, retry_after = await bucket.can_consume(1)
                assert can_consume is True

            # 11th request should fail
            can_consume, retry_after = await bucket.can_consume(1)
            assert can_consume is False

    async def test_retry_after_calculation(self, bucket):
        """Test retry-after calculation."""
        # Consume all tokens
        for _ in range(10):
            await bucket.can_consume(1)

        can_consume, retry_after = await bucket.can_consume(1)
        assert can_consume is False
        # Should need to wait 1 second for 1 token (60 tokens/minute = 1 token/second)
        assert retry_after == pytest.approx(1.0, rel=0.1)

    def test_is_expired(self, bucket):
        """Test bucket expiration."""
        assert not bucket.is_expired(max_idle_time=3600)
        
        # Mock old last_update time
        bucket.last_update = time.time() - 7200  # 2 hours ago
        assert bucket.is_expired(max_idle_time=3600)

    async def test_concurrent_access(self, bucket):
        """Test thread-safe access to bucket."""
        async def consume_token():
            return await bucket.can_consume(1)

        # Run multiple concurrent consumers
        tasks = [consume_token() for _ in range(20)]
        results = await asyncio.gather(*tasks)

        # Count successful consumptions
        successful = sum(1 for can_consume, _ in results if can_consume)
        assert successful == 10  # Only 10 tokens available


class TestRateLimiterService:
    """Test RateLimiterService implementation."""

    @pytest.fixture
    def rate_limiter(self):
        """Create a rate limiter service for testing."""
        return RateLimiterService()

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch('app.services.rate_limiter.settings') as mock:
            mock.rate_limiting_enabled = True
            mock.rate_limit_requests_per_minute = 60
            mock.rate_limit_burst_size = 10
            mock.rate_limit_upload_per_minute = 20
            mock.rate_limit_transcribe_per_minute = 10
            mock.rate_limit_health_per_minute = 120
            mock.rate_limit_cleanup_interval = 300
            yield mock

    def test_client_id_generation(self, rate_limiter):
        """Test client ID generation."""
        # IP only
        client_id = rate_limiter._get_client_id("192.168.1.1")
        assert client_id == "192.168.1.1"

        # IP + User-Agent
        client_id = rate_limiter._get_client_id("192.168.1.1", "Mozilla/5.0")
        assert "192.168.1.1:" in client_id
        assert len(client_id.split(":")) == 2

        # Same User-Agent should produce same hash
        client_id2 = rate_limiter._get_client_id("192.168.1.1", "Mozilla/5.0")
        assert client_id == client_id2

    def test_endpoint_limits(self, rate_limiter, mock_settings):
        """Test endpoint-specific limit configuration."""
        # Upload endpoint
        tokens, burst = rate_limiter._get_endpoint_limits("/api/v1/audio/upload")
        assert tokens == 20
        assert burst == 10

        # Transcribe endpoint
        tokens, burst = rate_limiter._get_endpoint_limits("/api/v1/audio/transcribe")
        assert tokens == 10
        assert burst == 10

        # Health endpoint
        tokens, burst = rate_limiter._get_endpoint_limits("/health")
        assert tokens == 120
        assert burst == 10

        # Default endpoint
        tokens, burst = rate_limiter._get_endpoint_limits("/api/v1/sessions")
        assert tokens == 60
        assert burst == 10

    async def test_rate_limit_check_allowed(self, rate_limiter, mock_settings):
        """Test rate limit check when requests are allowed."""
        allowed, retry_after, headers = await rate_limiter.check_rate_limit(
            ip="192.168.1.1",
            endpoint_path="/api/v1/health",
            user_agent="test-agent"
        )

        assert allowed is True
        assert retry_after == 0.0
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers
        assert headers["X-RateLimit-Limit"] == "120"

    async def test_rate_limit_check_exceeded(self, rate_limiter, mock_settings):
        """Test rate limit check when limit is exceeded."""
        # Consume all tokens for upload endpoint
        for _ in range(10):  # burst_size = 10
            await rate_limiter.check_rate_limit(
                ip="192.168.1.1",
                endpoint_path="/api/v1/audio/upload",
                user_agent="test-agent"
            )

        # Next request should be denied
        allowed, retry_after, headers = await rate_limiter.check_rate_limit(
            ip="192.168.1.1",
            endpoint_path="/api/v1/audio/upload",
            user_agent="test-agent"
        )

        assert allowed is False
        assert retry_after > 0.0
        assert "Retry-After" in headers
        assert headers["X-RateLimit-Remaining"] == "0"

    async def test_different_clients_independent(self, rate_limiter, mock_settings):
        """Test that different clients have independent rate limits."""
        # Consume all tokens for client 1
        for _ in range(10):
            await rate_limiter.check_rate_limit(
                ip="192.168.1.1",
                endpoint_path="/api/v1/audio/upload"
            )

        # Client 1 should be limited
        allowed, _, _ = await rate_limiter.check_rate_limit(
            ip="192.168.1.1",
            endpoint_path="/api/v1/audio/upload"
        )
        assert allowed is False

        # Client 2 should still be allowed
        allowed, _, _ = await rate_limiter.check_rate_limit(
            ip="192.168.1.2",
            endpoint_path="/api/v1/audio/upload"
        )
        assert allowed is True

    async def test_different_endpoints_independent(self, rate_limiter, mock_settings):
        """Test that different endpoints have independent rate limits."""
        # Consume all tokens for upload endpoint
        for _ in range(10):
            await rate_limiter.check_rate_limit(
                ip="192.168.1.1",
                endpoint_path="/api/v1/audio/upload"
            )

        # Upload should be limited
        allowed, _, _ = await rate_limiter.check_rate_limit(
            ip="192.168.1.1",
            endpoint_path="/api/v1/audio/upload"
        )
        assert allowed is False

        # Health endpoint should still be allowed
        allowed, _, _ = await rate_limiter.check_rate_limit(
            ip="192.168.1.1",
            endpoint_path="/health"
        )
        assert allowed is True

    async def test_rate_limiting_disabled(self, rate_limiter):
        """Test behavior when rate limiting is disabled."""
        with patch('app.services.rate_limiter.settings') as mock_settings:
            mock_settings.rate_limiting_enabled = False

            allowed, retry_after, headers = await rate_limiter.check_rate_limit(
                ip="192.168.1.1",
                endpoint_path="/api/v1/audio/upload"
            )

            assert allowed is True
            assert retry_after == 0.0
            assert headers == {}

    async def test_cleanup_expired_buckets(self, rate_limiter, mock_settings):
        """Test cleanup of expired rate limit buckets."""
        # Create some buckets
        await rate_limiter.check_rate_limit("192.168.1.1", "/test1")
        await rate_limiter.check_rate_limit("192.168.1.2", "/test2")
        
        initial_count = len(rate_limiter._buckets)
        assert initial_count > 0

        # Mock expired buckets
        for bucket in rate_limiter._buckets.values():
            bucket.last_update = time.time() - 7200  # 2 hours ago

        # Force cleanup by setting last cleanup time to old value
        rate_limiter._last_cleanup = time.time() - 400  # > cleanup_interval

        # Trigger cleanup
        await rate_limiter.check_rate_limit("192.168.1.3", "/test3")

        # All old buckets should be cleaned up, only new one remains
        assert len(rate_limiter._buckets) == 1

    async def test_get_stats(self, rate_limiter, mock_settings):
        """Test getting rate limiter statistics."""
        # Create some buckets
        await rate_limiter.check_rate_limit("192.168.1.1", "/test1")
        await rate_limiter.check_rate_limit("192.168.1.2", "/test2")

        stats = await rate_limiter.get_stats()
        
        assert "active_buckets" in stats
        assert "last_cleanup" in stats
        assert "cleanup_interval" in stats
        assert "enabled" in stats
        assert stats["active_buckets"] >= 2
        assert stats["enabled"] is True

    async def test_reset_client(self, rate_limiter, mock_settings):
        """Test resetting rate limits for a specific client."""
        # Create buckets for client
        await rate_limiter.check_rate_limit("192.168.1.1", "/test1")
        await rate_limiter.check_rate_limit("192.168.1.1", "/test2")
        await rate_limiter.check_rate_limit("192.168.1.2", "/test1")

        initial_count = len(rate_limiter._buckets)
        assert initial_count == 3

        # Reset client 1
        await rate_limiter.reset_client("192.168.1.1")

        # Should only have client 2's bucket remaining
        assert len(rate_limiter._buckets) == 1
        remaining_key = list(rate_limiter._buckets.keys())[0]
        assert "192.168.1.2" in remaining_key

    async def test_concurrent_rate_limiting(self, rate_limiter, mock_settings):
        """Test rate limiting under concurrent load."""
        async def make_request():
            allowed, _, _ = await rate_limiter.check_rate_limit(
                ip="192.168.1.1",
                endpoint_path="/api/v1/audio/upload"
            )
            return allowed

        # Make concurrent requests
        tasks = [make_request() for _ in range(20)]
        results = await asyncio.gather(*tasks)

        # Only burst_size (10) requests should be allowed
        allowed_count = sum(1 for allowed in results if allowed)
        assert allowed_count == 10