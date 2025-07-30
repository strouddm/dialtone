"""Validators for request data."""
import mimetypes
from pathlib import Path
from typing import BinaryIO, Optional

from fastapi import UploadFile

from app.core.exceptions import FileSizeError, UnsupportedFormatError, ValidationError

# Supported audio formats
SUPPORTED_AUDIO_FORMATS = ["audio/webm", "audio/mp4", "audio/m4a", "audio/mpeg"]
SUPPORTED_EXTENSIONS = [".webm", ".m4a", ".mp3", ".mp4"]

# File size limit (50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB in bytes


def validate_audio_file(file: UploadFile) -> None:
    """Validate uploaded audio file.

    Args:
        file: The uploaded file to validate

    Raises:
        ValidationError: If file validation fails
        FileSizeError: If file exceeds size limit
        UnsupportedFormatError: If file format is not supported
    """
    # Check if file exists
    if not file:
        raise ValidationError("No file provided")

    # Check filename
    if not file.filename:
        raise ValidationError("File has no filename")

    # Check content type
    content_type = file.content_type
    if not content_type:
        # Try to guess from filename
        content_type, _ = mimetypes.guess_type(file.filename)

    if content_type not in SUPPORTED_AUDIO_FORMATS:
        # Check extension as fallback
        extension = Path(file.filename).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFormatError(
                content_type or "unknown", SUPPORTED_AUDIO_FORMATS
            )

    # Check file size (if available)
    if hasattr(file, "size") and file.size is not None:
        if file.size > MAX_FILE_SIZE:
            raise FileSizeError(file.size, MAX_FILE_SIZE)


async def validate_file_size_async(file: UploadFile) -> None:
    """Validate file size by reading chunks asynchronously.

    Args:
        file: The uploaded file to validate

    Raises:
        FileSizeError: If file exceeds size limit
    """
    total_size = 0
    chunk_size = 1024 * 1024  # 1MB chunks

    # Reset file position
    await file.seek(0)

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break

        total_size += len(chunk)

        if total_size > MAX_FILE_SIZE:
            raise FileSizeError(total_size, MAX_FILE_SIZE)

    # Reset file position for further processing
    await file.seek(0)


def validate_content_type(
    content_type: Optional[str], filename: Optional[str] = None
) -> str:
    """Validate and normalize content type.

    Args:
        content_type: The content type to validate
        filename: Optional filename for fallback detection

    Returns:
        Normalized content type

    Raises:
        UnsupportedFormatError: If format is not supported
    """
    if not content_type and filename:
        content_type, _ = mimetypes.guess_type(filename)

    if not content_type:
        raise ValidationError("Cannot determine file type")

    # Normalize content type
    content_type = content_type.lower().strip()

    # Check if supported
    if content_type not in SUPPORTED_AUDIO_FORMATS:
        # Special case for m4a which might be detected as video/mp4
        if (
            content_type == "video/mp4"
            and filename
            and filename.lower().endswith(".m4a")
        ):
            return "audio/m4a"

        raise UnsupportedFormatError(content_type, SUPPORTED_AUDIO_FORMATS)

    return content_type
