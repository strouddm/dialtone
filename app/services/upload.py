"""Upload service for handling audio file uploads."""

import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

import aiofiles
from fastapi import UploadFile

from app.core.exceptions import (
    AudioProcessingError,
    FileSizeError,
    UnsupportedFormatError,
    ValidationError,
)
from app.core.settings import settings
from app.core.validators import validate_audio_file, validate_file_size_async

logger = logging.getLogger(__name__)


class UploadService:
    """Service for handling audio file uploads."""

    def __init__(self):
        """Initialize upload service."""
        self.upload_dir = settings.upload_dir
        self.max_size = settings.max_upload_size
        self.supported_types = settings.supported_audio_types

    async def validate_file(self, file: UploadFile) -> None:
        """Validate uploaded file."""
        # Use centralized validators
        validate_audio_file(file)
        
        # Additional async validation if needed
        await validate_file_size_async(file)

    def generate_upload_id(self) -> str:
        """Generate unique upload ID."""
        return str(uuid.uuid4())

    def generate_filename(self, upload_id: str, original_filename: str) -> str:
        """Generate safe filename for storage."""
        # Get file extension
        original_path = Path(original_filename)
        extension = original_path.suffix.lower()

        # Create timestamp
        timestamp = int(time.time())

        # Generate safe filename
        return f"{timestamp}_{upload_id}{extension}"

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal."""
        # Remove any path separators
        safe_name = Path(filename).name

        # Remove or replace dangerous characters
        dangerous_chars = ["<", ">", ":", '"', "|", "?", "*", "\0"]
        for char in dangerous_chars:
            safe_name = safe_name.replace(char, "_")

        return safe_name

    async def save_file(self, file: UploadFile, upload_id: str) -> tuple[str, int]:
        """Save uploaded file to disk."""
        try:
            # Create upload directory for this upload
            upload_path = self.upload_dir / upload_id
            upload_path.mkdir(parents=True, exist_ok=True)

            # Generate safe filename
            if not file.filename:
                raise ValueError("File has no filename")
            safe_original = self.sanitize_filename(file.filename)
            stored_filename = self.generate_filename(upload_id, safe_original)
            file_path = upload_path / stored_filename

            # Save file
            file_size = 0
            async with aiofiles.open(file_path, "wb") as f:
                while content := await file.read(8192):  # Read in 8KB chunks
                    file_size += len(content)

                    # Check size during upload
                    if file_size > self.max_size:
                        # Clean up partial file
                        try:
                            file_path.unlink()
                            upload_path.rmdir()
                        except Exception:
                            pass

                        raise FileSizeError(file_size, self.max_size)

                    await f.write(content)

            logger.info(
                "File uploaded successfully",
                extra={
                    "upload_id": upload_id,
                    "stored_filename": stored_filename,
                    "file_size": file_size,
                    "mime_type": file.content_type,
                },
            )

            return stored_filename, file_size

        except (ValidationError, FileSizeError, UnsupportedFormatError):
            raise
        except Exception as e:
            logger.error(
                "Failed to save uploaded file",
                extra={"upload_id": upload_id, "error": str(e)},
                exc_info=True,
            )
            raise AudioProcessingError(
                "Failed to save uploaded file",
                error_code="STORAGE_ERROR",
                details={"upload_id": upload_id}
            )

    async def process_upload(self, file: UploadFile) -> dict:
        """Process file upload from start to finish."""
        # Validate file
        await self.validate_file(file)

        # Generate upload ID
        upload_id = self.generate_upload_id()

        # Save file
        stored_filename, file_size = await self.save_file(file, upload_id)

        # Return upload metadata
        return {
            "upload_id": upload_id,
            "filename": stored_filename,
            "file_size": file_size,
            "mime_type": file.content_type,
            "status": "uploaded",
            "created_at": datetime.now(timezone.utc),
        }


# Global service instance
upload_service = UploadService()
