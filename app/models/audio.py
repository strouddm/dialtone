"""Audio upload models."""

from datetime import datetime
from typing import Literal

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
        "VALIDATION_ERROR"
    ] = Field(..., description="Machine-readable error code")
    max_size: int | None = Field(None, description="Maximum allowed file size")
    allowed_formats: list[str] | None = Field(None, description="Allowed MIME types")