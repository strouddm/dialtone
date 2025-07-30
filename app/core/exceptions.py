"""Custom exception hierarchy for the voice notes application."""
from typing import Any, Dict, Optional


class VoiceNotesError(Exception):
    """Base exception for all application errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize the error with message and metadata."""
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}


class ValidationError(VoiceNotesError):
    """400-level client errors for invalid requests."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize validation error with 400-level status."""
        super().__init__(message, 400, error_code, details)


class AudioValidationError(ValidationError):
    """Specific validation errors for audio files."""

    pass


class FileSizeError(ValidationError):
    """Error when file size exceeds limits."""

    def __init__(self, size: int, max_size: int) -> None:
        """Initialize with size information."""
        message = f"File size {size} bytes exceeds maximum {max_size} bytes"
        details = {"file_size": size, "max_size": max_size}
        super().__init__(message, "FILE_TOO_LARGE", details)
        self.status_code = 413


class UnsupportedFormatError(ValidationError):
    """Error when audio format is not supported."""

    def __init__(self, format: str, supported: list[str]) -> None:
        """Initialize with format information."""
        message = f"Format '{format}' not supported. Use: {', '.join(supported)}"
        details = {"format": format, "supported_formats": supported}
        super().__init__(message, "UNSUPPORTED_FORMAT", details)
        self.status_code = 422


class ServiceError(VoiceNotesError):
    """500-level server errors for service failures."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize service error with 500-level status."""
        super().__init__(message, 500, error_code, details)


class WhisperError(ServiceError):
    """Errors related to Whisper transcription service."""

    pass


class AudioProcessingError(ServiceError):
    """Errors during audio processing/conversion."""

    pass


class ResourceExhaustedError(ServiceError):
    """Error when system resources are exhausted."""

    def __init__(self, resource: str, message: Optional[str] = None) -> None:
        """Initialize with resource information."""
        msg = message or f"Resource exhausted: {resource}"
        details = {"resource": resource}
        super().__init__(msg, "RESOURCE_EXHAUSTED", details)
        self.status_code = 503


class RateLimitError(VoiceNotesError):
    """Error when rate limits are exceeded."""

    def __init__(self, retry_after: int) -> None:
        """Initialize with retry information."""
        message = f"Rate limit exceeded. Retry after {retry_after} seconds"
        details = {"retry_after": retry_after}
        super().__init__(message, 429, "RATE_LIMITED", details)
