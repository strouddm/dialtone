"""Tests for rate limiting middleware."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request, Response
from starlette.datastructures import Headers

from app.core.exceptions import RateLimitError
from app.core.middleware import RateLimitingMiddleware


class TestRateLimitingMiddleware:
    """Test RateLimitingMiddleware functionality."""

    @pytest.fixture
    def middleware(self):
        """Create rate limiting middleware instance."""
        app = MagicMock()
        return RateLimitingMiddleware(app)

    @pytest.fixture
    def mock_request(self):
        """Create a mock request for testing."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/audio/upload"
        request.headers = Headers({
            "user-agent": "Mozilla/5.0 Test Browser",
            "x-forwarded-for": "192.168.1.100, 10.0.0.1"
        })
        request.client.host = "10.0.0.1"
        return request

    @pytest.fixture
    def mock_call_next(self):
        """Create a mock call_next function."""
        async def call_next(request):
            response = MagicMock(spec=Response)
            response.headers = {}
            return response
        return call_next

    def test_get_client_ip_forwarded_for(self, middleware):
        """Test extracting client IP from X-Forwarded-For header."""
        request = MagicMock()
        request.headers.get.side_effect = lambda key: {
            "X-Forwarded-For": "192.168.1.100, 10.0.0.1",
            "X-Real-IP": None
        }.get(key)
        
        ip = middleware._get_client_ip(request)
        assert ip == "192.168.1.100"

    def test_get_client_ip_real_ip(self, middleware):
        """Test extracting client IP from X-Real-IP header."""
        request = MagicMock()
        request.headers.get.side_effect = lambda key: {
            "X-Forwarded-For": None,
            "X-Real-IP": "192.168.1.200"
        }.get(key)
        
        ip = middleware._get_client_ip(request)
        assert ip == "192.168.1.200"

    def test_get_client_ip_direct(self, middleware):
        """Test extracting client IP from direct connection."""
        request = MagicMock()
        request.headers.get.return_value = None
        request.client.host = "192.168.1.50"
        
        ip = middleware._get_client_ip(request)
        assert ip == "192.168.1.50"

    def test_get_client_ip_fallback(self, middleware):
        """Test fallback when no IP is available."""
        request = MagicMock()
        request.headers.get.return_value = None
        request.client = None
        
        ip = middleware._get_client_ip(request)
        assert ip == "unknown"

    def test_get_endpoint_limits_upload(self, middleware):
        """Test getting limits for upload endpoint."""
        with patch('app.core.middleware.settings') as mock_settings:
            mock_settings.rate_limit_upload_per_minute = 20
            mock_settings.rate_limit_burst_size = 10
            
            tokens, burst = middleware._get_endpoint_limits("/api/v1/audio/upload")
            assert tokens == 20
            assert burst == 10

    def test_get_endpoint_limits_transcribe(self, middleware):
        """Test getting limits for transcribe endpoint."""
        with patch('app.core.middleware.settings') as mock_settings:
            mock_settings.rate_limit_transcribe_per_minute = 15
            mock_settings.rate_limit_burst_size = 5
            
            tokens, burst = middleware._get_endpoint_limits("/api/v1/audio/transcribe")
            assert tokens == 15
            assert burst == 5

    def test_get_endpoint_limits_health(self, middleware):
        """Test getting limits for health endpoint."""
        with patch('app.core.middleware.settings') as mock_settings:
            mock_settings.rate_limit_health_per_minute = 100
            mock_settings.rate_limit_burst_size = 20
            
            tokens, burst = middleware._get_endpoint_limits("/health")
            assert tokens == 100
            assert burst == 20

    def test_get_endpoint_limits_default(self, middleware):
        """Test getting default limits for other endpoints."""
        with patch('app.core.middleware.settings') as mock_settings:
            mock_settings.rate_limit_requests_per_minute = 60
            mock_settings.rate_limit_burst_size = 10
            
            tokens, burst = middleware._get_endpoint_limits("/api/v1/sessions")
            assert tokens == 60
            assert burst == 10

    async def test_dispatch_allowed(self, middleware, mock_request, mock_call_next):
        """Test middleware when request is allowed."""
        with patch('app.core.middleware.rate_limiter') as mock_rate_limiter:
            # Mock rate limiter to allow request
            mock_rate_limiter.check_rate_limit.return_value = (
                True, 0.0, {"X-RateLimit-Limit": "20", "X-RateLimit-Remaining": "19"}
            )

            response = await middleware.dispatch(mock_request, mock_call_next)

            # Verify rate limiter was called correctly
            mock_rate_limiter.check_rate_limit.assert_called_once_with(
                ip="192.168.1.100",
                endpoint_path="/api/v1/audio/upload",
                user_agent="Mozilla/5.0 Test Browser"
            )

            # Verify headers were added
            assert response.headers["X-RateLimit-Limit"] == "20"
            assert response.headers["X-RateLimit-Remaining"] == "19"

    async def test_dispatch_rate_limited(self, middleware, mock_request, mock_call_next):
        """Test middleware when request is rate limited."""
        with patch('app.core.middleware.rate_limiter') as mock_rate_limiter:
            # Mock rate limiter to deny request
            mock_rate_limiter.check_rate_limit.return_value = (
                False, 30.0, {
                    "X-RateLimit-Limit": "20",
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": "31"
                }
            )
            
            with patch('app.core.middleware.RateLimitingMiddleware._get_endpoint_limits') as mock_limits:
                mock_limits.return_value = (20, 10)

                # Should raise RateLimitError
                with pytest.raises(RateLimitError) as exc_info:
                    await middleware.dispatch(mock_request, mock_call_next)

                # Verify exception details
                error = exc_info.value
                assert error.status_code == 429
                assert error.details["retry_after"] == 31
                assert error.details["limit"] == 20
                assert error.details["endpoint"] == "/api/v1/audio/upload"

    async def test_dispatch_no_user_agent(self, middleware, mock_call_next):
        """Test middleware when no User-Agent header is present."""
        request = MagicMock(spec=Request)
        request.url.path = "/health"
        request.headers = Headers({"x-forwarded-for": "192.168.1.100"})
        request.client.host = "10.0.0.1"

        with patch('app.core.middleware.rate_limiter') as mock_rate_limiter:
            mock_rate_limiter.check_rate_limit.return_value = (
                True, 0.0, {"X-RateLimit-Limit": "120"}
            )

            await middleware.dispatch(request, mock_call_next)

            # Verify rate limiter was called with None user agent
            mock_rate_limiter.check_rate_limit.assert_called_once_with(
                ip="192.168.1.100",
                endpoint_path="/health",
                user_agent=None
            )

    async def test_dispatch_with_complex_headers(self, middleware, mock_call_next):
        """Test middleware with complex forwarding headers."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/audio/transcribe"
        request.headers = Headers({
            "x-forwarded-for": "  203.0.113.1  ,  192.168.1.1,   10.0.0.1  ",
            "user-agent": "Custom-Client/1.0"
        })
        request.client.host = "10.0.0.1"

        with patch('app.core.middleware.rate_limiter') as mock_rate_limiter:
            mock_rate_limiter.check_rate_limit.return_value = (
                True, 0.0, {}
            )

            await middleware.dispatch(request, mock_call_next)

            # Should extract first IP and strip whitespace
            mock_rate_limiter.check_rate_limit.assert_called_once_with(
                ip="203.0.113.1",
                endpoint_path="/api/v1/audio/transcribe",
                user_agent="Custom-Client/1.0"
            )

    async def test_dispatch_integration_flow(self, middleware, mock_call_next):
        """Test full integration flow through middleware."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/audio/upload"
        request.headers = Headers({
            "x-forwarded-for": "192.168.1.100",
            "user-agent": "Test-Agent/1.0"
        })

        with patch('app.core.middleware.rate_limiter') as mock_rate_limiter, \
             patch('app.core.middleware.RateLimitingMiddleware._get_endpoint_limits') as mock_limits:
            
            mock_limits.return_value = (10, 5)
            mock_rate_limiter.check_rate_limit.return_value = (
                True, 0.0, {
                    "X-RateLimit-Limit": "10",
                    "X-RateLimit-Remaining": "4",
                    "X-RateLimit-Reset": "1234567890"
                }
            )

            response = await middleware.dispatch(request, mock_call_next)

            # Verify full call chain
            mock_rate_limiter.check_rate_limit.assert_called_once()
            assert response.headers["X-RateLimit-Limit"] == "10"
            assert response.headers["X-RateLimit-Remaining"] == "4"
            assert response.headers["X-RateLimit-Reset"] == "1234567890"

    async def test_error_handling_in_rate_check(self, middleware, mock_request, mock_call_next):
        """Test error handling when rate limiter fails."""
        with patch('app.core.middleware.rate_limiter') as mock_rate_limiter:
            # Mock rate limiter to raise an exception
            mock_rate_limiter.check_rate_limit.side_effect = Exception("Rate limiter error")

            # Should propagate the exception
            with pytest.raises(Exception, match="Rate limiter error"):
                await middleware.dispatch(mock_request, mock_call_next)

    async def test_header_merging(self, middleware, mock_request):
        """Test that rate limit headers are properly merged with response headers."""
        async def call_next_with_headers(request):
            response = MagicMock(spec=Response)
            response.headers = {"Content-Type": "application/json", "X-Custom": "value"}
            return response

        with patch('app.core.middleware.rate_limiter') as mock_rate_limiter:
            mock_rate_limiter.check_rate_limit.return_value = (
                True, 0.0, {
                    "X-RateLimit-Limit": "20",
                    "X-RateLimit-Remaining": "15"
                }
            )

            response = await middleware.dispatch(mock_request, call_next_with_headers)

            # Verify both original and rate limit headers are present
            assert response.headers["Content-Type"] == "application/json"
            assert response.headers["X-Custom"] == "value"
            assert response.headers["X-RateLimit-Limit"] == "20"
            assert response.headers["X-RateLimit-Remaining"] == "15"