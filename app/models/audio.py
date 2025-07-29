"""Audio upload and transcription models."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    """Response model for successful audio upload."""

    upload_id: str = Field(..., description="Unique identifier for the upload")
    filename: str = Field(..., description="Stored filename")
    file_size: int = Field(..., description="File size in bytes", ge=0)
    mime_type: str = Field(..., description="MIME type of the uploaded file")
    status: Literal["uploaded"] = Field("uploaded", description="Upload status")
    created_at: datetime = Field(..., description="Upload timestamp")


class UploadError(BaseModel):
    """Error response for upload failures."""

    error: str = Field(..., description="Error message")
    error_code: Literal[
        "FILE_TOO_LARGE",
        "INVALID_FORMAT",
        "MISSING_FILE",
        "STORAGE_ERROR",
        "VALIDATION_ERROR",
    ] = Field(..., description="Machine-readable error code")
    max_size: int | None = Field(None, description="Maximum allowed file size")
    allowed_formats: list[str] | None = Field(None, description="Allowed MIME types")


class TranscriptionRequest(BaseModel):
    """Request model for transcription."""

    upload_id: str = Field(..., description="Upload ID from audio upload")
    language: Optional[str] = Field(None, description="Expected language code (e.g., 'en', 'es')")


class TranscriptionData(BaseModel):
    """Transcription result data."""

    text: str = Field(..., description="Transcribed text content")
    language: str = Field(..., description="Detected language code")
    confidence: float = Field(..., description="Confidence score 0.0-1.0", ge=0.0, le=1.0)
    duration_seconds: float = Field(..., description="Audio duration in seconds", ge=0.0)


class TranscriptionResponse(BaseModel):
    """Response model for successful transcription."""

    upload_id: str = Field(..., description="Upload ID that was transcribed")
    transcription: TranscriptionData = Field(..., description="Transcription results")
    processing_time_seconds: float = Field(..., description="Time taken to process", ge=0.0)
    status: Literal["completed"] = Field("completed", description="Processing status")


class TranscriptionError(BaseModel):
    """Error response for transcription failures."""

    error: str = Field(..., description="Error message")
    error_code: Literal[
        "UPLOAD_NOT_FOUND",
        "AUDIO_FILE_NOT_FOUND", 
        "CONVERSION_ERROR",
        "TRANSCRIPTION_ERROR",
        "TRANSCRIPTION_TIMEOUT",
        "SERVICE_UNAVAILABLE",
        "PROCESSING_ERROR",
        "INVALID_AUDIO",
    ] = Field(..., description="Machine-readable error code")
    timeout_seconds: Optional[int] = Field(None, description="Timeout value if applicable")
