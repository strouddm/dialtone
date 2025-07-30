"""Common response models."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response model."""

    error: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Machine-readable error code")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )


class SuccessResponse(BaseModel):
    """Standard success response model."""

    success: bool = Field(True, description="Operation success status")
    message: str = Field(..., description="Success message")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
