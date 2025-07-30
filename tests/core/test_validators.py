"""Tests for validators."""
import pytest
from fastapi import UploadFile

from app.core.exceptions import FileSizeError, UnsupportedFormatError, ValidationError
from app.core.validators import (
    MAX_FILE_SIZE,
    SUPPORTED_AUDIO_FORMATS,
    SUPPORTED_EXTENSIONS,
    validate_audio_file,
    validate_content_type,
    validate_file_size_async,
)


class MockUploadFile:
    """Mock UploadFile for testing."""

    def __init__(self, filename=None, content_type=None, size=None, content=b""):
        self.filename = filename
        self.content_type = content_type
        self.size = size
        self.content = content
        self._position = 0

    async def read(self, size=-1):
        """Read content."""
        if size == -1:
            data = self.content[self._position :]
            self._position = len(self.content)
        else:
            data = self.content[self._position : self._position + size]
            self._position += len(data)
        return data

    async def seek(self, position):
        """Seek to position."""
        self._position = position


class TestValidateAudioFile:
    """Test audio file validation."""

    def test_no_file(self):
        """Test validation with no file."""
        with pytest.raises(ValidationError, match="No file provided"):
            validate_audio_file(None)

    def test_no_filename(self):
        """Test validation with no filename."""
        file = MockUploadFile(filename=None)
        with pytest.raises(ValidationError, match="File has no filename"):
            validate_audio_file(file)

    def test_valid_content_type(self):
        """Test validation with valid content type."""
        file = MockUploadFile(
            filename="audio.mp3",
            content_type="audio/mpeg",
            size=1000,
        )
        validate_audio_file(file)  # Should not raise

    def test_invalid_content_type(self):
        """Test validation with invalid content type."""
        file = MockUploadFile(
            filename="audio.wav",
            content_type="audio/wav",
            size=1000,
        )
        with pytest.raises(UnsupportedFormatError) as exc_info:
            validate_audio_file(file)
        assert "audio/wav" in str(exc_info.value)

    def test_valid_extension_fallback(self):
        """Test validation with valid extension when content type missing."""
        file = MockUploadFile(
            filename="audio.webm",
            content_type=None,
            size=1000,
        )
        validate_audio_file(file)  # Should not raise

    def test_file_too_large(self):
        """Test validation with file too large."""
        file = MockUploadFile(
            filename="audio.mp3",
            content_type="audio/mpeg",
            size=MAX_FILE_SIZE + 1,
        )
        with pytest.raises(FileSizeError) as exc_info:
            validate_audio_file(file)
        assert exc_info.value.details["file_size"] == MAX_FILE_SIZE + 1
        assert exc_info.value.details["max_size"] == MAX_FILE_SIZE


class TestValidateFileSizeAsync:
    """Test async file size validation."""

    @pytest.mark.asyncio
    async def test_file_within_limit(self):
        """Test file within size limit."""
        content = b"x" * 1000
        file = MockUploadFile(content=content)
        await validate_file_size_async(file)  # Should not raise
        assert file._position == 0  # Should reset position

    @pytest.mark.asyncio
    async def test_file_too_large(self):
        """Test file exceeding size limit."""
        content = b"x" * (MAX_FILE_SIZE + 1)
        file = MockUploadFile(content=content)
        with pytest.raises(FileSizeError) as exc_info:
            await validate_file_size_async(file)
        assert exc_info.value.details["file_size"] > MAX_FILE_SIZE

    @pytest.mark.asyncio
    async def test_chunked_reading(self):
        """Test that file is read in chunks."""
        content = b"x" * (2 * 1024 * 1024)  # 2MB
        file = MockUploadFile(content=content)
        await validate_file_size_async(file)
        assert file._position == 0  # Should reset


class TestValidateContentType:
    """Test content type validation."""

    def test_valid_content_type(self):
        """Test with valid content type."""
        result = validate_content_type("audio/mpeg")
        assert result == "audio/mpeg"

    def test_content_type_normalization(self):
        """Test content type is normalized."""
        result = validate_content_type(" AUDIO/MPEG ")
        assert result == "audio/mpeg"

    def test_no_content_type_with_filename(self):
        """Test fallback to filename detection."""
        result = validate_content_type(None, "audio.mp3")
        assert result == "audio/mpeg"

    def test_no_content_type_no_filename(self):
        """Test error when cannot determine type."""
        with pytest.raises(ValidationError, match="Cannot determine file type"):
            validate_content_type(None, None)

    def test_unsupported_content_type(self):
        """Test unsupported content type."""
        with pytest.raises(UnsupportedFormatError) as exc_info:
            validate_content_type("audio/wav")
        assert "audio/wav" in str(exc_info.value)

    def test_m4a_special_case(self):
        """Test M4A files detected as video/mp4."""
        result = validate_content_type("video/mp4", "audio.m4a")
        assert result == "audio/m4a"

    def test_m4a_without_proper_extension(self):
        """Test video/mp4 without M4A extension."""
        with pytest.raises(UnsupportedFormatError):
            validate_content_type("video/mp4", "video.mp4")
