"""Integration tests for rate limiting functionality."""

import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import create_app


class TestRateLimitingIntegration:
    """Integration tests for rate limiting with full application."""

    @pytest.fixture
    def app_with_rate_limiting(self):
        """Create app with rate limiting enabled."""
        with patch("app.core.settings.settings") as mock_settings:
            # Enable rate limiting with low limits for testing
            mock_settings.rate_limiting_enabled = True
            mock_settings.rate_limit_requests_per_minute = 60
            mock_settings.rate_limit_burst_size = 3
            mock_settings.rate_limit_upload_per_minute = 2
            mock_settings.rate_limit_transcribe_per_minute = 1
            mock_settings.rate_limit_health_per_minute = 10
            mock_settings.rate_limit_cleanup_interval = 300

            # Mock other required settings
            mock_settings.obsidian_vault_path = "/tmp/test-vault"
            mock_settings.upload_dir = "/tmp/test-uploads"
            mock_settings.session_storage_dir = "/tmp/test-sessions"
            mock_settings.ollama_enabled = False
            mock_settings.app_name = "Test Dialtone"
            mock_settings.debug = True

            yield create_app()

    @pytest.fixture
    def app_without_rate_limiting(self):
        """Create app with rate limiting disabled."""
        with patch("app.core.settings.settings") as mock_settings:
            # Disable rate limiting
            mock_settings.rate_limiting_enabled = False

            # Mock other required settings
            mock_settings.obsidian_vault_path = "/tmp/test-vault"
            mock_settings.upload_dir = "/tmp/test-uploads"
            mock_settings.session_storage_dir = "/tmp/test-sessions"
            mock_settings.ollama_enabled = False
            mock_settings.app_name = "Test Dialtone"
            mock_settings.debug = True

            yield create_app()

    def test_health_endpoint_rate_limiting(self, app_with_rate_limiting):
        """Test rate limiting on health endpoint."""
        client = TestClient(app_with_rate_limiting)

        # First few requests should succeed
        for i in range(3):
            response = client.get("/health")
            assert response.status_code == 200
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert int(response.headers["X-RateLimit-Remaining"]) == 2 - i

        # Next request should be rate limited
        response = client.get("/health")
        assert response.status_code == 429
        assert "Retry-After" in response.headers
        assert response.json()["error_code"] == "RATE_LIMITED"

    def test_different_endpoints_independent_limits(self, app_with_rate_limiting):
        """Test that different endpoints have independent rate limits."""
        client = TestClient(app_with_rate_limiting)

        # Exhaust health endpoint limit
        for _ in range(3):
            response = client.get("/health")
            assert response.status_code == 200

        # Health endpoint should be limited
        response = client.get("/health")
        assert response.status_code == 429

        # But API info endpoint should still work (uses default limit)
        response = client.get("/api")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers

    def test_rate_limiting_headers(self, app_with_rate_limiting):
        """Test that proper rate limiting headers are returned."""
        client = TestClient(app_with_rate_limiting)

        response = client.get("/health")
        assert response.status_code == 200

        # Check required headers
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

        # Verify header values
        assert int(response.headers["X-RateLimit-Limit"]) > 0
        assert int(response.headers["X-RateLimit-Remaining"]) >= 0
        assert int(response.headers["X-RateLimit-Reset"]) > 0

    def test_rate_limiting_disabled(self, app_without_rate_limiting):
        """Test that requests work normally when rate limiting is disabled."""
        client = TestClient(app_without_rate_limiting)

        # Make many requests - all should succeed
        for _ in range(20):
            response = client.get("/health")
            assert response.status_code == 200
            # No rate limit headers should be present
            assert "X-RateLimit-Limit" not in response.headers

    def test_different_clients_independent(self, app_with_rate_limiting):
        """Test that different clients have independent rate limits."""
        # Client 1
        client1 = TestClient(app_with_rate_limiting)

        # Client 2 with different headers to simulate different client
        client2 = TestClient(app_with_rate_limiting)
        client2.headers.update({"User-Agent": "Different-Client/1.0"})

        # Exhaust client 1's limit
        for _ in range(3):
            response = client1.get("/health")
            assert response.status_code == 200

        # Client 1 should be limited
        response = client1.get("/health")
        assert response.status_code == 429

        # Client 2 should still work
        response = client2.get("/health")
        assert response.status_code == 200

    def test_rate_limit_error_details(self, app_with_rate_limiting):
        """Test that rate limit error contains proper details."""
        client = TestClient(app_with_rate_limiting)

        # Exhaust limit
        for _ in range(3):
            client.get("/health")

        # Get rate limited response
        response = client.get("/health")
        assert response.status_code == 429

        error_data = response.json()
        assert error_data["error_code"] == "RATE_LIMITED"
        assert "retry_after" in error_data["details"]
        assert "limit" in error_data["details"]
        assert "endpoint" in error_data["details"]
        assert error_data["details"]["endpoint"] == "/health"

    def test_concurrent_requests_rate_limiting(self, app_with_rate_limiting):
        """Test rate limiting under concurrent load."""

        async def make_request(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get("/health")
                return response.status_code

        async def run_concurrent_test():
            # Make many concurrent requests
            tasks = [make_request(app_with_rate_limiting) for _ in range(10)]
            status_codes = await asyncio.gather(*tasks)
            return status_codes

        status_codes = asyncio.run(run_concurrent_test())

        # Only burst_size (3) requests should succeed
        success_count = sum(1 for code in status_codes if code == 200)
        rate_limited_count = sum(1 for code in status_codes if code == 429)

        assert success_count == 3
        assert rate_limited_count == 7

    def test_rate_limit_recovery_over_time(self, app_with_rate_limiting):
        """Test that rate limits recover over time."""
        client = TestClient(app_with_rate_limiting)

        # Exhaust limit
        for _ in range(3):
            response = client.get("/health")
            assert response.status_code == 200

        # Should be rate limited
        response = client.get("/health")
        assert response.status_code == 429

        # Mock time advancement to allow token recovery
        with patch("time.time") as mock_time:
            import time

            original_time = time.time()

            # Advance time by 1 minute to allow full recovery
            mock_time.return_value = original_time + 60

            # Should be able to make requests again
            response = client.get("/health")
            assert response.status_code == 200

    def test_forwarded_ip_handling(self, app_with_rate_limiting):
        """Test that X-Forwarded-For header is properly handled."""
        client = TestClient(app_with_rate_limiting)

        # Make requests with X-Forwarded-For header
        headers = {"X-Forwarded-For": "203.0.113.195"}

        # Exhaust limit for this IP
        for _ in range(3):
            response = client.get("/health", headers=headers)
            assert response.status_code == 200

        # Should be rate limited
        response = client.get("/health", headers=headers)
        assert response.status_code == 429

        # Request without header (different "client") should work
        response = client.get("/health")
        assert response.status_code == 200

    def test_complex_endpoint_paths(self, app_with_rate_limiting):
        """Test rate limiting with complex endpoint paths."""
        client = TestClient(app_with_rate_limiting)

        # Test with query parameters
        response = client.get("/health?check=full")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers

        # Test with trailing slash
        response = client.get("/api/")
        assert response.status_code == 404  # This endpoint doesn't exist
        # But should still have rate limit headers if middleware ran
        # (depends on middleware order vs 404 handling)

    @pytest.mark.asyncio
    async def test_rate_limiter_stats_endpoint(self, app_with_rate_limiting):
        """Test accessing rate limiter statistics (if exposed)."""
        # This tests internal stats functionality
        from app.services.rate_limiter import rate_limiter

        # Make some requests to generate stats
        client = TestClient(app_with_rate_limiting)
        for _ in range(2):
            client.get("/health")

        # Get stats
        stats = await rate_limiter.get_stats()
        assert "active_buckets" in stats
        assert "enabled" in stats
        assert stats["enabled"] is True
        assert stats["active_buckets"] > 0

    def test_error_response_format(self, app_with_rate_limiting):
        """Test that rate limit error response follows standard format."""
        client = TestClient(app_with_rate_limiting)

        # Exhaust limit
        for _ in range(3):
            client.get("/health")

        # Get rate limited response
        response = client.get("/health")
        assert response.status_code == 429

        # Verify response format matches ErrorResponse model
        data = response.json()
        required_fields = ["error", "error_code", "details"]
        for field in required_fields:
            assert field in data

        # Verify specific rate limit fields
        assert data["error_code"] == "RATE_LIMITED"
        assert "retry_after" in data["details"]

    def test_middleware_ordering(self, app_with_rate_limiting):
        """Test that middleware executes in correct order."""
        client = TestClient(app_with_rate_limiting)

        response = client.get("/health")
        assert response.status_code == 200

        # Should have both request ID and rate limit headers
        assert "X-Request-ID" in response.headers
        assert "X-RateLimit-Limit" in response.headers
        assert "X-Process-Time" in response.headers
