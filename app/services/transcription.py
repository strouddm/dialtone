"""Transcription orchestration service."""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import HTTPException, status

from app.core.settings import settings
from app.services.audio_converter import audio_converter
from app.services.ollama import ollama_service
from app.services.whisper_model import whisper_manager

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Service for orchestrating complete transcription workflow."""

    def __init__(self):
        """Initialize transcription service."""
        self.max_concurrent = settings.max_concurrent_transcriptions
        self.timeout_seconds = settings.transcription_timeout
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        self._active_transcriptions: Dict[str, asyncio.Task] = {}

    async def transcribe_upload(
        self,
        upload_id: str,
        language: Optional[str] = None,
        include_summary: bool = False,
        max_summary_words: int = 150,
    ) -> Dict[str, Any]:
        """Transcribe uploaded audio file by upload_id."""
        # Get upload directory
        upload_dir = settings.upload_dir / upload_id
        if not upload_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": f"Upload {upload_id} not found",
                    "error_code": "UPLOAD_NOT_FOUND",
                },
            )

        # Find audio file in upload directory
        audio_files = list(upload_dir.glob("*"))
        if not audio_files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": f"No audio file found for upload {upload_id}",
                    "error_code": "AUDIO_FILE_NOT_FOUND",
                },
            )

        audio_file = audio_files[0]  # Should only be one file per upload

        logger.info(
            "Starting transcription for upload",
            extra={"upload_id": upload_id, "audio_file": str(audio_file)},
        )

        return await self.transcribe_file(
            audio_file, upload_id, language, include_summary, max_summary_words
        )

    async def transcribe_file(
        self,
        audio_file: Path,
        upload_id: str,
        language: Optional[str] = None,
        include_summary: bool = False,
        max_summary_words: int = 150,
    ) -> Dict[str, Any]:
        """Transcribe a specific audio file."""
        start_time = time.time()

        async with self._semaphore:
            try:
                # Ensure Whisper model is loaded
                if not whisper_manager.is_loaded:
                    if whisper_manager.is_loading:
                        # Wait for model to finish loading
                        while whisper_manager.is_loading:
                            await asyncio.sleep(0.1)

                    if not whisper_manager.is_loaded:
                        await whisper_manager.load_model()

                # Get audio file info
                audio_info = await audio_converter.get_audio_info(audio_file)

                logger.info(
                    "Audio file info",
                    extra={
                        "upload_id": upload_id,
                        "duration": audio_info["duration"],
                        "format": audio_info["format"],
                        "sample_rate": audio_info["sample_rate"],
                        "channels": audio_info["channels"],
                    },
                )

                # Convert audio if needed
                processed_audio_path = audio_file
                conversion_needed = audio_converter.is_conversion_needed(audio_file)

                if conversion_needed:
                    logger.info(
                        "Converting audio for Whisper compatibility",
                        extra={
                            "upload_id": upload_id,
                            "original_format": audio_info["format"],
                        },
                    )

                    (
                        processed_audio_path,
                        duration,
                    ) = await audio_converter.convert_to_whisper_format(
                        audio_file, audio_file.parent
                    )
                else:
                    duration = audio_info["duration"]

                # Perform transcription with timeout
                try:
                    transcription_task = asyncio.create_task(
                        whisper_manager.transcribe(
                            str(processed_audio_path),
                            language=language,
                        )
                    )

                    self._active_transcriptions[upload_id] = transcription_task

                    result = await asyncio.wait_for(
                        transcription_task, timeout=self.timeout_seconds
                    )

                finally:
                    # Clean up task tracking
                    self._active_transcriptions.pop(upload_id, None)

                    # Clean up converted file if we created one
                    if conversion_needed and processed_audio_path != audio_file:
                        try:
                            processed_audio_path.unlink()
                            logger.info(
                                "Cleaned up converted audio file",
                                extra={
                                    "upload_id": upload_id,
                                    "file": str(processed_audio_path),
                                },
                            )
                        except Exception as e:
                            logger.warning(
                                "Failed to clean up converted file",
                                extra={
                                    "upload_id": upload_id,
                                    "file": str(processed_audio_path),
                                    "error": str(e),
                                },
                            )

                # Generate summary if requested
                summary = None
                summary_processing_time = None

                if include_summary:
                    summary_start_time = time.time()
                    transcription_text = result.get("text", "").strip()

                    if transcription_text:
                        try:
                            # Check if Ollama service is available
                            if await ollama_service.health_check():
                                logger.info(
                                    "Generating summary for transcription",
                                    extra={
                                        "upload_id": upload_id,
                                        "text_length": len(transcription_text),
                                        "max_words": max_summary_words,
                                    },
                                )
                                summary = await ollama_service.generate_summary(
                                    transcription_text, max_summary_words
                                )
                                summary_processing_time = round(
                                    time.time() - summary_start_time, 2
                                )
                                logger.info(
                                    "Summary generated successfully",
                                    extra={
                                        "upload_id": upload_id,
                                        "summary_length": len(summary)
                                        if summary
                                        else 0,
                                        "summary_time": summary_processing_time,
                                    },
                                )
                            else:
                                logger.warning(
                                    "Ollama service unavailable, skipping summary generation",
                                    extra={"upload_id": upload_id},
                                )
                                summary = None
                        except Exception as e:
                            logger.warning(
                                "Failed to generate summary, continuing without it",
                                extra={
                                    "upload_id": upload_id,
                                    "error": str(e),
                                },
                            )
                            summary = None
                    else:
                        logger.info(
                            "No transcription text available for summarization",
                            extra={"upload_id": upload_id},
                        )

                # Extract keywords if enabled
                keywords = None
                keyword_processing_time = None

                if settings.keyword_extraction_enabled:
                    keyword_start_time = time.time()
                    transcription_text = result.get("text", "").strip()

                    if transcription_text:
                        try:
                            # Check if Ollama service is available
                            if await ollama_service.health_check():
                                logger.info(
                                    "Extracting keywords from transcription",
                                    extra={
                                        "upload_id": upload_id,
                                        "text_length": len(transcription_text),
                                        "max_keywords": settings.keyword_max_count,
                                    },
                                )
                                keywords = await ollama_service.extract_keywords(
                                    transcription_text, settings.keyword_max_count
                                )
                                keyword_processing_time = round(
                                    time.time() - keyword_start_time, 2
                                )
                                logger.info(
                                    "Keywords extracted successfully",
                                    extra={
                                        "upload_id": upload_id,
                                        "keyword_count": len(keywords)
                                        if keywords
                                        else 0,
                                        "keyword_time": keyword_processing_time,
                                        "keywords": keywords[:3]
                                        if keywords
                                        else [],  # Log first 3 for debugging
                                    },
                                )
                            else:
                                logger.warning(
                                    "Ollama service unavailable, skipping keyword extraction",
                                    extra={"upload_id": upload_id},
                                )
                                keywords = []
                        except Exception as e:
                            logger.warning(
                                "Failed to extract keywords, continuing without them",
                                extra={
                                    "upload_id": upload_id,
                                    "error": str(e),
                                },
                            )
                            keywords = []
                    else:
                        logger.info(
                            "No transcription text available for keyword extraction",
                            extra={"upload_id": upload_id},
                        )
                        keywords = []

                processing_time = time.time() - start_time

                # Format response
                response: Dict[str, Any] = {
                    "upload_id": upload_id,
                    "transcription": {
                        "text": result.get("text", "").strip(),
                        "language": result.get("language", "unknown"),
                        "confidence": self._calculate_confidence(result),
                        "duration_seconds": duration,
                    },
                    "processing_time_seconds": round(processing_time, 2),
                    "status": "completed",
                }

                # Add summary fields if requested (even if generation failed)
                if include_summary:
                    response["summary"] = summary
                    response["summary_processing_time"] = summary_processing_time

                # Add keyword fields if extraction is enabled
                if settings.keyword_extraction_enabled:
                    response["keywords"] = keywords
                    response["keyword_processing_time"] = keyword_processing_time

                logger.info(
                    "Transcription completed successfully",
                    extra={
                        "upload_id": upload_id,
                        "processing_time": processing_time,
                        "text_length": len(response["transcription"]["text"]),
                        "language": response["transcription"]["language"],
                        "summary_generated": summary is not None,
                        "summary_time": summary_processing_time,
                        "keywords_extracted": keywords is not None and len(keywords) > 0
                        if keywords
                        else False,
                        "keyword_count": len(keywords) if keywords else 0,
                        "keyword_time": keyword_processing_time,
                    },
                )

                return response

            except asyncio.TimeoutError:
                error_msg = (
                    f"Transcription timeout after {self.timeout_seconds} seconds"
                )
                logger.error(
                    "Transcription timeout",
                    extra={"upload_id": upload_id, "timeout": self.timeout_seconds},
                )
                raise HTTPException(
                    status_code=status.HTTP_408_REQUEST_TIMEOUT,
                    detail={
                        "error": error_msg,
                        "error_code": "TRANSCRIPTION_TIMEOUT",
                        "timeout_seconds": self.timeout_seconds,
                    },
                )

            except HTTPException:
                # Re-raise HTTP exceptions
                raise

            except Exception as e:
                error_msg = f"Transcription failed: {str(e)}"
                logger.error(
                    "Transcription error",
                    extra={"upload_id": upload_id, "error": error_msg},
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "error": "Transcription processing failed",
                        "error_code": "TRANSCRIPTION_ERROR",
                    },
                ) from e

    def _calculate_confidence(self, whisper_result: Dict[str, Any]) -> float:
        """Calculate overall confidence score from Whisper result."""
        # Whisper doesn't provide direct confidence scores
        # We estimate based on available metrics
        segments = whisper_result.get("segments", [])

        if not segments:
            return 0.5  # Default moderate confidence

        # Calculate average confidence from segments if available
        confidences = []
        for segment in segments:
            # Some Whisper versions include avg_logprob
            if "avg_logprob" in segment:
                # Convert log probability to confidence (rough approximation)
                conf = max(0.0, min(1.0, (segment["avg_logprob"] + 1.0)))
                confidences.append(conf)

        if confidences:
            return float(round(sum(confidences) / len(confidences), 2))

        # Fallback: estimate based on text characteristics
        text = whisper_result.get("text", "").strip()
        if not text:
            return 0.1

        # Simple heuristic: longer, more structured text = higher confidence
        words = text.split()
        if len(words) < 5:
            return 0.6
        elif len(words) < 20:
            return 0.7
        else:
            return 0.8

    async def get_transcription_status(self, upload_id: str) -> Dict[str, Any]:
        """Get status of active transcription."""
        if upload_id in self._active_transcriptions:
            task = self._active_transcriptions[upload_id]
            return {
                "upload_id": upload_id,
                "status": "processing" if not task.done() else "completed",
                "is_done": task.done(),
            }

        return {
            "upload_id": upload_id,
            "status": "not_found",
            "is_done": True,
        }

    async def cancel_transcription(self, upload_id: str) -> bool:
        """Cancel active transcription if running."""
        if upload_id in self._active_transcriptions:
            task = self._active_transcriptions[upload_id]
            if not task.done():
                task.cancel()
                logger.info(
                    "Transcription cancelled",
                    extra={"upload_id": upload_id},
                )
                return True
        return False

    def get_service_status(self) -> Dict[str, Any]:
        """Get transcription service status."""
        return {
            "max_concurrent": self.max_concurrent,
            "timeout_seconds": self.timeout_seconds,
            "active_transcriptions": len(self._active_transcriptions),
            "available_slots": self._semaphore._value,
            "whisper_model": whisper_manager.get_model_info(),
        }


# Global service instance
transcription_service = TranscriptionService()
