"""Exception handlers for FastAPI application."""
import logging

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import (
    RateLimitError,
    ServiceError,
    VoiceNotesError,
)
from app.models.common import ErrorResponse

logger = logging.getLogger(__name__)


async def voice_notes_error_handler(
    request: Request, exc: VoiceNotesError
) -> JSONResponse:
    """Handle custom VoiceNotesError exceptions."""
    request_id = getattr(request.state, "request_id", None)

    error_response = ErrorResponse(
        error=exc.message,
        error_code=exc.error_code,
        request_id=request_id,
        details=exc.details,
    )

    # Log error with context
    logger.error(
        "Error handling request",
        extra={
            "request_id": request_id,
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
            "details": exc.details,
        },
        exc_info=True if isinstance(exc, ServiceError) else False,
    )

    # Add retry-after header for rate limit errors
    headers = {}
    if isinstance(exc, RateLimitError) and "retry_after" in exc.details:
        headers["Retry-After"] = str(exc.details["retry_after"])

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(exclude_none=True),
        headers=headers,
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors."""
    request_id = getattr(request.state, "request_id", None)

    # Extract validation errors
    errors = []
    for error in exc.errors():
        field_path = " -> ".join(str(loc) for loc in error["loc"])
        errors.append(
            {
                "field": field_path,
                "message": error["msg"],
                "type": error["type"],
            }
        )

    error_response = ErrorResponse(
        error="Validation failed",
        error_code="VALIDATION_ERROR",
        request_id=request_id,
        details={"validation_errors": errors},
    )

    logger.warning(
        "Validation error",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "errors": errors,
        },
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.model_dump(exclude_none=True),
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle standard HTTP exceptions."""
    request_id = getattr(request.state, "request_id", None)

    # Use status code reason phrase if no detail provided
    if exc.detail:
        error_message = exc.detail
    else:
        from http import HTTPStatus

        try:
            error_message = HTTPStatus(exc.status_code).phrase
        except ValueError:
            error_message = "HTTP error occurred"

    error_response = ErrorResponse(
        error=error_message,
        error_code=f"HTTP_{exc.status_code}",
        request_id=request_id,
        details=None,
    )

    logger.warning(
        "HTTP exception",
        extra={
            "request_id": request_id,
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(exclude_none=True),
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    request_id = getattr(request.state, "request_id", None)

    # Log full traceback for unexpected errors
    logger.error(
        "Unexpected error",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "error_type": type(exc).__name__,
        },
        exc_info=True,
    )

    # Don't expose internal errors to users
    error_response = ErrorResponse(
        error="An internal error occurred",
        error_code="INTERNAL_ERROR",
        request_id=request_id,
        details=None,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(exclude_none=True),
    )
