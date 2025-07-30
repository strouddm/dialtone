"""Audio upload API endpoints."""

import logging
from typing import Union

from fastapi import APIRouter, File, Request, UploadFile, status

from app.models.audio import (
    TranscriptionRequest,
    TranscriptionResponse,
    UploadResponse,
)
from app.models.common import ErrorResponse
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
        400: {"model": ErrorResponse, "description": "Invalid file or missing file"},
        413: {"model": ErrorResponse, "description": "File too large"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Server error"},
    },
)
async def upload_audio(
    request: Request,
    file: UploadFile = File(..., description="Audio file to upload (WebM, M4A, MP3)"),
) -> UploadResponse:
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

    # Process the upload - exceptions will be handled by middleware
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


@router.post(
    "/transcribe",
    response_model=TranscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Transcribe uploaded audio",
    description="Transcribe an uploaded audio file using Whisper AI",
    responses={
        200: {"model": TranscriptionResponse, "description": "Transcription completed successfully"},
        400: {"model": ErrorResponse, "description": "Invalid audio format or conversion error"},
        404: {"model": ErrorResponse, "description": "Upload not found"},
        408: {"model": ErrorResponse, "description": "Transcription timeout"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Transcription processing error"},
        503: {"model": ErrorResponse, "description": "Transcription service unavailable"},
    },
)
async def transcribe_audio(
    request: Request,
    transcription_request: TranscriptionRequest,
) -> TranscriptionResponse:
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

    # Process transcription - exceptions will be handled by middleware
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
