"""Audio upload API endpoints."""

import logging
from typing import Union

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse

from app.models.audio import (
    TranscriptionError,
    TranscriptionRequest,
    TranscriptionResponse,
    UploadError,
    UploadResponse,
)
from app.services.transcription import transcription_service
from app.services.upload import upload_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/audio", tags=["audio"])


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload audio file",
    description="Upload an audio file for transcription and processing",
    responses={
        200: {"model": UploadResponse, "description": "File uploaded successfully"},
        400: {"model": UploadError, "description": "Invalid file or missing file"},
        413: {"model": UploadError, "description": "File too large"},
        422: {"description": "Validation error"},
        500: {"model": UploadError, "description": "Server error"},
    },
)
async def upload_audio(
    request: Request,
    file: UploadFile = File(..., description="Audio file to upload (WebM, M4A, MP3)"),
) -> Union[UploadResponse, JSONResponse]:
    """
    Upload an audio file for processing.

    Accepts audio files in WebM, M4A, and MP3 formats up to 50MB.
    Returns an upload ID that can be used to track processing status.

    - **file**: Audio file to upload (multipart/form-data)
    """
    request_id = getattr(request.state, "request_id", "unknown")

    logger.info(
        "Audio upload started",
        extra={
            "request_id": request_id,
            "upload_filename": file.filename,
            "content_type": file.content_type,
            "file_size": getattr(file, "size", "unknown"),
        },
    )

    try:
        # Process the upload
        upload_data = await upload_service.process_upload(file)

        logger.info(
            "Audio upload completed",
            extra={
                "request_id": request_id,
                "upload_id": upload_data["upload_id"],
                "stored_filename": upload_data["filename"],
                "file_size": upload_data["file_size"],
            },
        )

        return UploadResponse(**upload_data)

    except HTTPException as e:
        # Log the error but don't expose internal details
        logger.warning(
            "Audio upload failed",
            extra={
                "request_id": request_id,
                "upload_filename": file.filename,
                "error": str(e.detail),
                "status_code": e.status_code,
            },
        )

        # Enhance error response with request ID
        error_detail = e.detail
        if isinstance(error_detail, dict):
            error_detail["request_id"] = request_id

        return JSONResponse(status_code=e.status_code, content=error_detail)

    except Exception as e:
        # Handle unexpected errors
        logger.error(
            "Unexpected error during audio upload",
            extra={
                "request_id": request_id,
                "upload_filename": file.filename,
                "error": str(e),
            },
            exc_info=True,
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "error_code": "INTERNAL_ERROR",
                "request_id": request_id,
            },
        )


@router.post(
    "/transcribe",
    response_model=TranscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Transcribe uploaded audio",
    description="Transcribe an uploaded audio file using Whisper AI",
    responses={
        200: {"model": TranscriptionResponse, "description": "Transcription completed successfully"},
        400: {"model": TranscriptionError, "description": "Invalid audio format or conversion error"},
        404: {"model": TranscriptionError, "description": "Upload not found"},
        408: {"model": TranscriptionError, "description": "Transcription timeout"},
        422: {"description": "Validation error"},
        500: {"model": TranscriptionError, "description": "Transcription processing error"},
        503: {"model": TranscriptionError, "description": "Transcription service unavailable"},
    },
)
async def transcribe_audio(
    request: Request,
    transcription_request: TranscriptionRequest,
) -> Union[TranscriptionResponse, JSONResponse]:
    """
    Transcribe an uploaded audio file using Whisper AI.

    Takes an upload ID from a previous upload and transcribes the audio content.
    Uses OpenAI Whisper for local, privacy-first transcription.

    - **upload_id**: ID from successful audio upload
    - **language**: Optional language hint (e.g., 'en', 'es', 'fr')
    """
    request_id = getattr(request.state, "request_id", "unknown")
    upload_id = transcription_request.upload_id

    logger.info(
        "Transcription request started",
        extra={
            "request_id": request_id,
            "upload_id": upload_id,
            "language": transcription_request.language,
        },
    )

    try:
        # Process transcription
        transcription_data = await transcription_service.transcribe_upload(
            upload_id=upload_id,
            language=transcription_request.language,
        )

        logger.info(
            "Transcription completed successfully",
            extra={
                "request_id": request_id,
                "upload_id": upload_id,
                "processing_time": transcription_data["processing_time_seconds"],
                "text_length": len(transcription_data["transcription"]["text"]),
                "detected_language": transcription_data["transcription"]["language"],
            },
        )

        return TranscriptionResponse(**transcription_data)

    except HTTPException as e:
        # Log the error but don't expose internal details
        logger.warning(
            "Transcription request failed",
            extra={
                "request_id": request_id,
                "upload_id": upload_id,
                "error": str(e.detail),
                "status_code": e.status_code,
            },
        )

        # Enhance error response with request ID
        error_detail = e.detail
        if isinstance(error_detail, dict):
            error_detail["request_id"] = request_id

        return JSONResponse(status_code=e.status_code, content=error_detail)

    except Exception as e:
        # Handle unexpected errors
        logger.error(
            "Unexpected error during transcription",
            extra={
                "request_id": request_id,
                "upload_id": upload_id,
                "error": str(e),
            },
            exc_info=True,
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal transcription error",
                "error_code": "TRANSCRIPTION_ERROR",
                "request_id": request_id,
            },
        )
