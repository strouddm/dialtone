"""Whisper model management service with singleton pattern."""

import logging
import threading
from typing import Any, Dict, Optional

import whisper
from whisper import Whisper

from app.core.exceptions import ResourceExhaustedError, ServiceError, WhisperError
from app.core.settings import settings

logger = logging.getLogger(__name__)


class WhisperModelManager:
    """Singleton manager for Whisper model loading and transcription."""

    _instance: Optional["WhisperModelManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "WhisperModelManager":
        """Create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize model manager."""
        if hasattr(self, "_initialized"):
            return

        self._model: Optional[Whisper] = None
        self._model_size = settings.whisper_model_size
        self._device = settings.whisper_device
        self._compute_type = settings.whisper_compute_type
        self._loading = False
        self._load_error: Optional[str] = None
        self._initialized = True

        logger.info(
            "Whisper model manager initialized",
            extra={
                "model_size": self._model_size,
                "device": self._device,
                "compute_type": self._compute_type,
            },
        )

    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded and ready."""
        return self._model is not None

    @property
    def is_loading(self) -> bool:
        """Check if model is currently loading."""
        return self._loading

    @property
    def load_error(self) -> Optional[str]:
        """Get last loading error if any."""
        return self._load_error

    async def load_model(self) -> None:
        """Load Whisper model asynchronously."""
        if self._model is not None:
            return

        if self._loading:
            logger.info("Model already loading, waiting...")
            return

        with self._lock:
            if self._model is not None:
                return

            if self._loading:
                return

            self._loading = True
            self._load_error = None

        try:
            logger.info(
                "Loading Whisper model",
                extra={
                    "model_size": self._model_size,
                    "device": self._device,
                },
            )

            # Load model - this is CPU intensive but runs in thread pool
            self._model = whisper.load_model(
                name=self._model_size,
                device=self._device,
            )

            logger.info(
                "Whisper model loaded successfully",
                extra={
                    "model_size": self._model_size,
                    "device": self._device,
                },
            )

        except MemoryError as e:
            error_msg = f"Insufficient memory to load Whisper model: {str(e)}"
            self._load_error = error_msg
            logger.error(
                "Whisper model loading failed - memory error",
                extra={"error": error_msg},
                exc_info=True,
            )
            raise ResourceExhaustedError("memory", error_msg) from e
        except Exception as e:
            error_msg = f"Failed to load Whisper model: {str(e)}"
            self._load_error = error_msg
            logger.error(
                "Whisper model loading failed",
                extra={"error": error_msg},
                exc_info=True,
            )
            raise WhisperError(
                error_msg,
                error_code="MODEL_LOAD_ERROR",
                details={"model_size": self._model_size, "device": self._device},
            ) from e

        finally:
            self._loading = False

    async def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        task: str = "transcribe",
    ) -> Dict[str, Any]:
        """Transcribe audio file using loaded model."""
        if self._model is None:
            raise WhisperError(
                "Whisper model not loaded",
                error_code="MODEL_NOT_LOADED",
                details={"loading": self.is_loading, "load_error": self.load_error},
            )

        try:
            logger.info(
                "Starting transcription",
                extra={
                    "audio_path": audio_path,
                    "language": language,
                    "task": task,
                },
            )

            # Transcribe audio
            result = self._model.transcribe(
                audio=audio_path,
                language=language,
                task=task,
                fp16=False,  # Use fp32 for CPU compatibility
                verbose=False,  # Reduce logging noise
            )

            logger.info(
                "Transcription completed",
                extra={
                    "audio_path": audio_path,
                    "text_length": len(result.get("text", "")),
                    "language": result.get("language"),
                    "duration": result.get("duration"),
                },
            )

            return result

        except MemoryError as e:
            error_msg = f"Insufficient memory for transcription: {str(e)}"
            logger.error(
                "Transcription failed - memory error",
                extra={
                    "audio_path": audio_path,
                    "error": error_msg,
                },
                exc_info=True,
            )
            raise ResourceExhaustedError("memory", error_msg) from e
        except Exception as e:
            error_msg = f"Transcription failed: {str(e)}"
            logger.error(
                "Transcription error",
                extra={
                    "audio_path": audio_path,
                    "error": error_msg,
                },
                exc_info=True,
            )
            raise WhisperError(
                error_msg,
                error_code="TRANSCRIPTION_ERROR",
                details={"audio_path": audio_path},
            ) from e

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        return {
            "model_size": self._model_size,
            "device": self._device,
            "compute_type": self._compute_type,
            "is_loaded": self.is_loaded,
            "is_loading": self.is_loading,
            "load_error": self.load_error,
        }


# Global singleton instance
whisper_manager = WhisperModelManager()
