"""Tests for exception handlers."""

import pytest
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import (
    RateLimitError,
    ServiceError,
    ValidationError,
    VoiceNotesError,
)
from app.core.handlers import (
    general_exception_handler,
    http_exception_handler,
    validation_error_handler,
    voice_notes_error_handler,
)


class MockRequest:
    """Mock request for testing."""

    def __init__(self, request_id="test-123"):
        self.state = type("State", (), {"request_id": request_id})()
        self.url = type("URL", (), {"path": "/test/path"})()
        self.method = "POST"


@pytest.mark.asyncio
class TestVoiceNotesErrorHandler:
    """Test VoiceNotesError handler."""

    async def test_basic_error(self):
        """Test handling basic VoiceNotesError."""
        request = MockRequest()
        exc = VoiceNotesError("Test error", status_code=400, error_code="TEST_ERROR")

        response = await voice_notes_error_handler(request, exc)

        assert response.status_code == 400
        content = response.body
        assert b"Test error" in content
        assert b"TEST_ERROR" in content
        assert b"test-123" in content

    async def test_with_details(self):
        """Test handling error with details."""
        request = MockRequest()
        exc = ValidationError(
            "Invalid input",
            details={"field": "audio", "reason": "too large"},
        )

        response = await voice_notes_error_handler(request, exc)

        assert response.status_code == 400
        content = response.body
        assert b"Invalid input" in content
        assert b"audio" in content

    async def test_rate_limit_error(self):
        """Test handling rate limit error with retry header."""
        request = MockRequest()
        exc = RateLimitError(retry_after=60)

        response = await voice_notes_error_handler(request, exc)

        assert response.status_code == 429
        assert response.headers["Retry-After"] == "60"

    async def test_service_error_logging(self):
        """Test that service errors log stack traces."""
        request = MockRequest()
        exc = ServiceError("Database connection failed")

        response = await voice_notes_error_handler(request, exc)

        assert response.status_code == 500
        content = response.body
        assert b"Database connection failed" in content


@pytest.mark.asyncio
class TestValidationErrorHandler:
    """Test validation error handler."""

    async def test_pydantic_validation_error(self):
        """Test handling Pydantic validation errors."""
        request = MockRequest()

        # Create mock validation error
        errors = [
            {
                "loc": ("body", "upload_id"),
                "msg": "field required",
                "type": "value_error.missing",
            },
            {
                "loc": ("body", "language"),
                "msg": "invalid language code",
                "type": "value_error",
            },
        ]

        class MockValidationError:
            def errors(self):
                return errors

        exc = MockValidationError()

        response = await validation_error_handler(request, exc)

        assert response.status_code == 422
        content = response.body
        assert b"Validation failed" in content
        assert b"field required" in content
        assert b"invalid language code" in content


@pytest.mark.asyncio
class TestHTTPExceptionHandler:
    """Test HTTP exception handler."""

    async def test_http_exception_with_detail(self):
        """Test handling HTTP exception with detail."""
        request = MockRequest()
        exc = StarletteHTTPException(status_code=404, detail="Resource not found")

        response = await http_exception_handler(request, exc)

        assert response.status_code == 404
        content = response.body
        assert b"Resource not found" in content
        assert b"HTTP_404" in content

    async def test_http_exception_without_detail(self):
        """Test handling HTTP exception without detail."""
        request = MockRequest()
        exc = StarletteHTTPException(status_code=503)

        response = await http_exception_handler(request, exc)

        assert response.status_code == 503
        content = response.body
        assert b"Service Unavailable" in content  # Proper HTTP status phrase
        assert b"HTTP_503" in content


@pytest.mark.asyncio
class TestGeneralExceptionHandler:
    """Test general exception handler."""

    async def test_unexpected_error(self):
        """Test handling unexpected exceptions."""
        request = MockRequest()
        exc = RuntimeError("Unexpected error occurred")

        response = await general_exception_handler(request, exc)

        assert response.status_code == 500
        content = response.body
        assert b"An internal error occurred" in content
        assert b"INTERNAL_ERROR" in content
        assert b"test-123" in content
        # Should not expose internal error details
        assert b"Unexpected error occurred" not in content

    async def test_no_request_id(self):
        """Test handling when request has no ID."""
        request = MockRequest(request_id=None)
        request.state.request_id = None
        exc = Exception("Some error")

        response = await general_exception_handler(request, exc)

        assert response.status_code == 500
        # Should still handle gracefully
        content = response.body
        assert b"An internal error occurred" in content
