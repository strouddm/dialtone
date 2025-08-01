"""Audio upload API endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, File, Form, Request, UploadFile, status

from app.models.audio import TranscriptionRequest, TranscriptionResponse, UploadResponse
from app.models.common import ErrorResponse
from app.models.session import AudioMetadata, SessionStatus
from app.services.session_manager import session_manager
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
        200: {
            "model": UploadResponse,
            "description": "File uploaded successfully",
            "content": {
                "application/json": {
                    "example": {
                        "upload_id": "upload_20241130_143052_abc123",
                        "filename": "voice_note_20241130_143052.webm",
                        "file_size": 1024576,
                        "mime_type": "audio/webm",
                        "status": "uploaded",
                        "created_at": "2024-11-30T14:30:52.123456",
                    }
                }
            },
        },
        400: {
            "model": ErrorResponse,
            "description": "Invalid file or missing file",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_file": {
                            "summary": "No file provided",
                            "value": {
                                "error": "No file provided",
                                "error_code": "MISSING_FILE",
                                "request_id": "req_123456789",
                            },
                        },
                        "invalid_format": {
                            "summary": "Unsupported file format",
                            "value": {
                                "error": "Unsupported file format. "
                                "Only WebM, M4A, and MP3 are allowed",
                                "error_code": "INVALID_FORMAT",
                                "request_id": "req_123456789",
                                "details": {
                                    "allowed_formats": [
                                        "audio/webm",
                                        "audio/mp4",
                                        "audio/mpeg",
                                    ]
                                },
                            },
                        },
                    }
                }
            },
        },
        413: {
            "model": ErrorResponse,
            "description": "File too large (max 50MB)",
            "content": {
                "application/json": {
                    "example": {
                        "error": "File size exceeds maximum allowed size of 50MB",
                        "error_code": "FILE_TOO_LARGE",
                        "request_id": "req_123456789",
                        "details": {"max_size": 52428800, "received_size": 62914560},
                    }
                }
            },
        },
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Server error"},
    },
)
async def upload_audio(
    request: Request,
    file: UploadFile = File(..., description="Audio file to upload (WebM, M4A, MP3)"),
    session_id: Optional[str] = Form(
        None, description="Optional session ID for workflow tracking"
    ),
) -> UploadResponse:
    """
    Upload an audio file for processing.

    Accepts audio files in WebM, M4A, and MP3 formats up to 50MB.
    Returns an upload ID that can be used to track processing status.

    - **file**: Audio file to upload (multipart/form-data)
    - **session_id**: Optional session ID to associate upload with existing session
    """
    request_id = getattr(request.state, "request_id", "unknown")

    logger.info(
        "Audio upload started",
        extra={
            "request_id": request_id,
            "upload_filename": file.filename,
            "content_type": file.content_type,
            "file_size": getattr(file, "size", "unknown"),
            "session_id": session_id,
        },
    )

    # Process the upload - exceptions will be handled by middleware
    upload_data = await upload_service.process_upload(file)

    # Associate with session if provided
    if session_id:
        try:
            audio_metadata = AudioMetadata(
                upload_id=upload_data["upload_id"],
                filename=upload_data["filename"],
                file_size=upload_data["file_size"],
                mime_type=upload_data.get("mime_type", "audio/unknown"),
            )
            await session_manager.update_session_data(
                session_id,
                audio_metadata=audio_metadata,
                status=SessionStatus.PROCESSING,
            )
            logger.info(
                "Upload associated with session",
                extra={
                    "request_id": request_id,
                    "upload_id": upload_data["upload_id"],
                    "session_id": session_id,
                },
            )
        except Exception as e:
            logger.warning(
                f"Failed to update session {session_id} with upload data: {e}",
                extra={"request_id": request_id, "session_id": session_id},
            )

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
        200: {
            "model": TranscriptionResponse,
            "description": "Transcription completed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "upload_id": "upload_20241130_143052_abc123",
                        "transcription": {
                            "text": "This is a test transcription of my voice note about the project meeting tomorrow.",
                            "language": "en",
                            "confidence": 0.95,
                            "duration_seconds": 12.5,
                        },
                        "summary": "- Project meeting scheduled for tomorrow\n- Key topics to discuss identified\n- Voice note captured for reference",
                        "summary_processing_time": 1.2,
                        "keywords": ["project", "meeting", "tomorrow", "voice-note"],
                        "keyword_processing_time": 0.8,
                        "processing_time_seconds": 2.8,
                        "status": "completed",
                    }
                }
            },
        },
        400: {
            "model": ErrorResponse,
            "description": "Invalid audio format or conversion error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Audio conversion failed: unsupported codec",
                        "error_code": "CONVERSION_ERROR",
                        "request_id": "req_123456789",
                    }
                }
            },
        },
        404: {
            "model": ErrorResponse,
            "description": "Upload not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Upload with ID 'invalid_upload_id' not found",
                        "error_code": "UPLOAD_NOT_FOUND",
                        "request_id": "req_123456789",
                    }
                }
            },
        },
        408: {
            "model": ErrorResponse,
            "description": "Transcription timeout",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Transcription exceeded timeout limit",
                        "error_code": "TRANSCRIPTION_TIMEOUT",
                        "request_id": "req_123456789",
                        "details": {"timeout_seconds": 30},
                    }
                }
            },
        },
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Transcription processing error"},
        503: {
            "model": ErrorResponse,
            "description": "Transcription service unavailable",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Whisper transcription service is currently unavailable",
                        "error_code": "SERVICE_UNAVAILABLE",
                        "request_id": "req_123456789",
                    }
                }
            },
        },
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
    Optionally generates AI bullet-point summaries and extracts keywords using Ollama.

    - **upload_id**: ID from successful audio upload
    - **language**: Optional language hint (e.g., 'en', 'es', 'fr')
    - **include_summary**: Generate AI summary of transcription (default: false)
    - **max_summary_words**: Maximum words in summary, 50-300 (default: 150)

    **Keyword Extraction**: Automatically extracts 3-5 keywords when enabled in configuration.
    Keywords are returned in the response when Ollama service is available and keyword
    extraction is enabled (default: true). This is controlled globally, not per-request.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    upload_id = transcription_request.upload_id

    logger.info(
        "Transcription request started",
        extra={
            "request_id": request_id,
            "upload_id": upload_id,
            "language": transcription_request.language,
            "session_id": transcription_request.session_id,
        },
    )

    # Process transcription - exceptions will be handled by middleware
    transcription_data = await transcription_service.transcribe_upload(
        upload_id=upload_id,
        language=transcription_request.language,
        include_summary=transcription_request.include_summary,
        max_summary_words=transcription_request.max_summary_words or 150,
    )

    # Update session with transcription results if session_id provided
    if transcription_request.session_id:
        try:
            from app.models.session import TranscriptionData as SessionTranscriptionData

            session_transcription = SessionTranscriptionData(
                text=transcription_data["transcription"]["text"],
                language=transcription_data["transcription"]["language"],
                confidence=transcription_data["transcription"]["confidence"],
                processing_time_seconds=transcription_data["processing_time_seconds"],
            )

            update_data = {
                "transcription": session_transcription,
                "status": SessionStatus.TRANSCRIBED,
                "transcription_time": transcription_data["processing_time_seconds"],
            }

            # Add summary and keywords if available
            if transcription_data.get("summary"):
                update_data["summary"] = transcription_data["summary"]
                update_data["summary_time"] = transcription_data.get(
                    "summary_processing_time"
                )
                update_data["status"] = SessionStatus.SUMMARIZED

            if transcription_data.get("keywords"):
                update_data["keywords"] = transcription_data["keywords"]
                update_data["keyword_time"] = transcription_data.get(
                    "keyword_processing_time"
                )

            await session_manager.update_session_data(
                transcription_request.session_id, **update_data
            )

            logger.info(
                "Transcription results saved to session",
                extra={
                    "request_id": request_id,
                    "upload_id": upload_id,
                    "session_id": transcription_request.session_id,
                },
            )
        except Exception as e:
            logger.warning(
                f"Failed to update session {transcription_request.session_id} with transcription: {e}",
                extra={
                    "request_id": request_id,
                    "session_id": transcription_request.session_id,
                },
            )

    logger.info(
        "Transcription completed successfully",
        extra={
            "request_id": request_id,
            "upload_id": upload_id,
            "processing_time": transcription_data["processing_time_seconds"],
            "text_length": len(transcription_data["transcription"]["text"]),
            "detected_language": transcription_data["transcription"]["language"],
            "summary_included": transcription_data.get("summary") is not None,
            "summary_processing_time": transcription_data.get(
                "summary_processing_time"
            ),
            "keywords_extracted": transcription_data.get("keywords") is not None,
            "keyword_count": len(transcription_data["keywords"])
            if transcription_data.get("keywords")
            else 0,
            "keyword_processing_time": transcription_data.get(
                "keyword_processing_time"
            ),
        },
    )

    return TranscriptionResponse(**transcription_data)
