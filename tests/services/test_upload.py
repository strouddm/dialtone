"""Tests for upload service."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from fastapi import HTTPException, UploadFile
from io import BytesIO

from app.services.upload import UploadService


@pytest.fixture
def upload_service():
    """Create upload service instance for testing."""
    return UploadService()


@pytest.fixture
def mock_upload_file():
    """Create mock upload file."""
    file = Mock(spec=UploadFile)
    file.filename = "test_audio.webm"
    file.content_type = "audio/webm"
    file.size = 1024
    file.read = AsyncMock(return_value=b"fake audio data")
    return file


@pytest.fixture
def large_mock_file():
    """Create mock file that's too large."""
    file = Mock(spec=UploadFile)
    file.filename = "large_audio.webm"
    file.content_type = "audio/webm"
    file.size = 100 * 1024 * 1024  # 100MB - larger than 50MB limit
    return file


@pytest.fixture
def invalid_format_file():
    """Create mock file with invalid format."""
    file = Mock(spec=UploadFile)
    file.filename = "invalid.txt"
    file.content_type = "text/plain"
    file.size = 1024
    return file


class TestUploadService:
    """Test upload service functionality."""
    
    def test_generate_upload_id(self, upload_service):
        """Test upload ID generation."""
        upload_id = upload_service.generate_upload_id()
        assert isinstance(upload_id, str)
        assert len(upload_id) == 36  # UUID4 format
        assert "-" in upload_id
    
    def test_generate_filename(self, upload_service):
        """Test filename generation."""
        upload_id = "test-123"
        original = "test_audio.webm"
        
        filename = upload_service.generate_filename(upload_id, original)
        
        assert filename.endswith("_test-123.webm")
        assert filename.startswith(str(int(filename.split("_")[0])))  # Timestamp
    
    def test_sanitize_filename(self, upload_service):
        """Test filename sanitization."""
        dangerous_name = "test<>:\"|?*audio.webm"
        safe_name = upload_service.sanitize_filename(dangerous_name)
        
        assert "<" not in safe_name
        assert ">" not in safe_name
        assert ":" not in safe_name
        assert '"' not in safe_name
        assert "|" not in safe_name
        assert "?" not in safe_name
        assert "*" not in safe_name
        assert safe_name == "test________audio.webm"
    
    @pytest.mark.asyncio
    async def test_validate_file_success(self, upload_service, mock_upload_file):
        """Test successful file validation."""
        # Should not raise exception
        await upload_service.validate_file(mock_upload_file)
    
    @pytest.mark.asyncio
    async def test_validate_file_no_filename(self, upload_service):
        """Test validation with missing filename."""
        file = Mock(spec=UploadFile)
        file.filename = None
        
        with pytest.raises(HTTPException) as exc_info:
            await upload_service.validate_file(file)
        
        assert exc_info.value.status_code == 400
        assert "MISSING_FILE" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_validate_file_too_large(self, upload_service, large_mock_file):
        """Test validation with file too large."""
        with pytest.raises(HTTPException) as exc_info:
            await upload_service.validate_file(large_mock_file)
        
        assert exc_info.value.status_code == 413
        assert "FILE_TOO_LARGE" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_validate_file_invalid_format(self, upload_service, invalid_format_file):
        """Test validation with invalid format."""
        with pytest.raises(HTTPException) as exc_info:
            await upload_service.validate_file(invalid_format_file)
        
        assert exc_info.value.status_code == 400
        assert "INVALID_FORMAT" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_save_file_success(self, upload_service, mock_upload_file, tmp_path):
        """Test successful file saving."""
        # Mock the upload directory
        upload_service.upload_dir = tmp_path
        upload_id = "test-upload-123"
        
        # Mock file reading
        mock_upload_file.read = AsyncMock(side_effect=[b"test data", b""])
        
        filename, size = await upload_service.save_file(mock_upload_file, upload_id)
        
        assert isinstance(filename, str)
        assert filename.endswith(".webm")
        assert size == 9  # Length of "test data"
        
        # Check file was created
        upload_path = tmp_path / upload_id
        assert upload_path.exists()
        assert (upload_path / filename).exists()
    
    @pytest.mark.asyncio
    async def test_save_file_size_exceeded_during_upload(self, upload_service, tmp_path):
        """Test file size check during upload."""
        upload_service.upload_dir = tmp_path
        upload_service.max_size = 10  # Very small limit
        
        file = Mock(spec=UploadFile)
        file.filename = "test.webm"
        file.content_type = "audio/webm"
        file.size = 5  # Smaller than limit initially
        
        # Mock reading that exceeds limit
        file.read = AsyncMock(side_effect=[b"x" * 15, b""])  # 15 bytes exceeds 10 byte limit
        
        with pytest.raises(HTTPException) as exc_info:
            await upload_service.save_file(file, "test-id")
        
        assert exc_info.value.status_code == 413
    
    @pytest.mark.asyncio
    async def test_process_upload_success(self, upload_service, mock_upload_file, tmp_path):
        """Test complete upload process."""
        upload_service.upload_dir = tmp_path
        mock_upload_file.read = AsyncMock(side_effect=[b"test audio data", b""])
        
        result = await upload_service.process_upload(mock_upload_file)
        
        assert "upload_id" in result
        assert "filename" in result
        assert "file_size" in result
        assert "mime_type" in result
        assert "status" in result
        assert "created_at" in result
        
        assert result["status"] == "uploaded"
        assert result["mime_type"] == "audio/webm"
        assert result["file_size"] == 15  # Length of "test audio data"
    
    @pytest.mark.asyncio
    async def test_process_upload_validation_failure(self, upload_service, invalid_format_file):
        """Test upload process with validation failure."""
        with pytest.raises(HTTPException) as exc_info:
            await upload_service.process_upload(invalid_format_file)
        
        assert exc_info.value.status_code == 400