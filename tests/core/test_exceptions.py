"""Tests for custom exceptions."""

from app.core.exceptions import (
    FileSizeError,
    RateLimitError,
    ResourceExhaustedError,
    ServiceError,
    UnsupportedFormatError,
    ValidationError,
    VoiceNotesError,
    WhisperError,
)


class TestVoiceNotesError:
    """Test base exception class."""

    def test_basic_creation(self):
        """Test creating basic exception."""
        exc = VoiceNotesError("Test error")
        assert str(exc) == "Test error"
        assert exc.message == "Test error"
        assert exc.status_code == 500
        assert exc.error_code == "VoiceNotesError"
        assert exc.details == {}

    def test_with_all_params(self):
        """Test creating exception with all parameters."""
        exc = VoiceNotesError(
            "Test error",
            status_code=400,
            error_code="TEST_ERROR",
            details={"key": "value"},
        )
        assert exc.message == "Test error"
        assert exc.status_code == 400
        assert exc.error_code == "TEST_ERROR"
        assert exc.details == {"key": "value"}


class TestValidationError:
    """Test validation error class."""

    def test_default_status_code(self):
        """Test validation error has 400 status code."""
        exc = ValidationError("Invalid input")
        assert exc.status_code == 400
        assert exc.message == "Invalid input"

    def test_with_details(self):
        """Test validation error with details."""
        exc = ValidationError(
            "Invalid format",
            error_code="INVALID_FORMAT",
            details={"field": "audio", "expected": "mp3"},
        )
        assert exc.status_code == 400
        assert exc.error_code == "INVALID_FORMAT"
        assert exc.details["field"] == "audio"


class TestFileSizeError:
    """Test file size error class."""

    def test_file_size_error(self):
        """Test file size error creation."""
        exc = FileSizeError(size=60_000_000, max_size=50_000_000)
        assert exc.status_code == 413
        assert exc.error_code == "FILE_TOO_LARGE"
        assert "60000000 bytes exceeds maximum 50000000 bytes" in exc.message
        assert exc.details["file_size"] == 60_000_000
        assert exc.details["max_size"] == 50_000_000


class TestUnsupportedFormatError:
    """Test unsupported format error class."""

    def test_unsupported_format(self):
        """Test unsupported format error."""
        supported = ["audio/mp3", "audio/webm"]
        exc = UnsupportedFormatError("audio/wav", supported)
        assert exc.status_code == 422
        assert exc.error_code == "UNSUPPORTED_FORMAT"
        assert "audio/wav" in exc.message
        assert "audio/mp3, audio/webm" in exc.message
        assert exc.details["format"] == "audio/wav"
        assert exc.details["supported_formats"] == supported


class TestServiceError:
    """Test service error class."""

    def test_default_status_code(self):
        """Test service error has 500 status code."""
        exc = ServiceError("Service failed")
        assert exc.status_code == 500
        assert exc.message == "Service failed"


class TestWhisperError:
    """Test Whisper error class."""

    def test_whisper_error(self):
        """Test Whisper error is a service error."""
        exc = WhisperError("Model loading failed")
        assert isinstance(exc, ServiceError)
        assert exc.status_code == 500


class TestResourceExhaustedError:
    """Test resource exhausted error class."""

    def test_with_resource_only(self):
        """Test with resource parameter only."""
        exc = ResourceExhaustedError("memory")
        assert exc.status_code == 503
        assert exc.error_code == "RESOURCE_EXHAUSTED"
        assert exc.message == "Resource exhausted: memory"
        assert exc.details["resource"] == "memory"

    def test_with_custom_message(self):
        """Test with custom message."""
        exc = ResourceExhaustedError("cpu", "All CPU cores are busy")
        assert exc.status_code == 503
        assert exc.message == "All CPU cores are busy"
        assert exc.details["resource"] == "cpu"


class TestRateLimitError:
    """Test rate limit error class."""

    def test_rate_limit_error(self):
        """Test rate limit error creation."""
        exc = RateLimitError(retry_after=60)
        assert exc.status_code == 429
        assert exc.error_code == "RATE_LIMITED"
        assert "Retry after 60 seconds" in exc.message
        assert exc.details["retry_after"] == 60
