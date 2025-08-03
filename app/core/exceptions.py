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


class AudioProcessingError(ServiceError):
    """Errors during audio processing/conversion."""


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

    def __init__(
        self,
        retry_after: int,
        limit: Optional[int] = None,
        endpoint: Optional[str] = None,
    ) -> None:
        """Initialize with retry information."""
        message = f"Rate limit exceeded. Retry after {retry_after} seconds"
        details = {
            "retry_after": retry_after,
            "limit": limit,
            "endpoint": endpoint,
        }
        super().__init__(message, 429, "RATE_LIMITED", details)


class ServiceUnavailableError(ServiceError):
    """Error when a required service is unavailable."""

    def __init__(self, message: str, service: Optional[str] = None) -> None:
        """Initialize with service information."""
        details = {"service": service} if service else {}
        super().__init__(message, "SERVICE_UNAVAILABLE", details)
        self.status_code = 503


class NotFoundError(VoiceNotesError):
    """404-level errors for missing resources."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize not found error with 404 status."""
        super().__init__(message, 404, error_code, details)


class VaultError(VoiceNotesError):
    """Base exception for vault operations."""

    def __init__(
        self,
        message: str = "Vault operation failed",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize vault error."""
        super().__init__(
            message=message,
            status_code=500,
            error_code="VAULT_ERROR",
            details=details,
        )


class VaultAccessError(VaultError):
    """Vault access permission error."""

    def __init__(
        self,
        message: str = "Unable to access vault",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize vault access error."""
        super().__init__(message=message, details=details)
        self.error_code = "VAULT_ACCESS_ERROR"


class VaultWriteError(VaultError):
    """File writing error."""

    def __init__(
        self,
        message: str = "Failed to write file to vault",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize vault write error."""
        super().__init__(message=message, details=details)
        self.error_code = "VAULT_WRITE_ERROR"


class VaultConfigurationError(VaultError):
    """Vault configuration error."""

    def __init__(
        self,
        message: str = "Vault configuration is invalid",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize vault configuration error."""
        super().__init__(message=message, details=details)
        self.error_code = "VAULT_CONFIG_ERROR"
        self.status_code = 503
