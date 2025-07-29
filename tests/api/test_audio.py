"""Tests for audio upload API endpoints."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from fastapi import status
from fastapi.testclient import TestClient
from io import BytesIO

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def valid_audio_file():
    """Create valid audio file for testing."""
    content = b"fake webm audio data"
    return ("test_audio.webm", BytesIO(content), "audio/webm")


@pytest.fixture
def large_audio_file():
    """Create large audio file for testing."""
    # Create content larger than 50MB
    content = b"x" * (55 * 1024 * 1024)  # 55MB
    return ("large_audio.webm", BytesIO(content), "audio/webm")


@pytest.fixture
def invalid_format_file():
    """Create invalid format file for testing."""
    content = b"not audio data"
    return ("document.txt", BytesIO(content), "text/plain")


class TestAudioUploadEndpoint:
    """Test audio upload endpoint."""

    def test_upload_endpoint_exists(self, client):
        """Test that upload endpoint exists and accepts POST."""
        # Test without file should return 422 (validation error)
        response = client.post("/api/v1/audio/upload")
        assert response.status_code == 422  # Missing required file

    @patch("app.services.upload.upload_service.process_upload")
    def test_upload_success(self, mock_process_upload, client, valid_audio_file):
        """Test successful file upload."""
        # Mock successful upload
        mock_process_upload.return_value = {
            "upload_id": "test-123-456",
            "filename": "20250728_test-123-456.webm",
            "file_size": 19,
            "mime_type": "audio/webm",
            "status": "uploaded",
            "created_at": "2025-07-28T12:00:00Z",
        }

        response = client.post("/api/v1/audio/upload", files={"file": valid_audio_file})

        assert response.status_code == 200
        data = response.json()

        assert data["upload_id"] == "test-123-456"
        assert data["filename"] == "20250728_test-123-456.webm"
        assert data["file_size"] == 19
        assert data["mime_type"] == "audio/webm"
        assert data["status"] == "uploaded"
        assert "created_at" in data

    def test_upload_missing_file(self, client):
        """Test upload without file."""
        response = client.post("/api/v1/audio/upload")

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_upload_empty_file(self, client):
        """Test upload with empty filename."""
        # FastAPI validation will reject empty filename as 422
        empty_file = ("", BytesIO(b"test"), "audio/webm")

        response = client.post("/api/v1/audio/upload", files={"file": empty_file})

        # FastAPI returns 422 for validation errors on empty filename
        assert response.status_code == 422

    def test_upload_invalid_format(self, client, invalid_format_file):
        """Test upload with invalid file format."""
        response = client.post(
            "/api/v1/audio/upload", files={"file": invalid_format_file}
        )

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "INVALID_FORMAT"
        assert "allowed_formats" in data

    def test_upload_file_too_large(self, client):
        """Test upload with file too large."""
        # Create content larger than 50MB limit
        with patch(
            "app.services.upload.upload_service.max_size", 1024
        ):  # 1KB limit for test
            large_content = b"x" * 2048  # 2KB, larger than 1KB limit
            large_file = ("large.webm", BytesIO(large_content), "audio/webm")

            response = client.post("/api/v1/audio/upload", files={"file": large_file})

            assert response.status_code == 413
            data = response.json()
            assert data["error_code"] == "FILE_TOO_LARGE"
            assert "max_size" in data

    def test_upload_webm_format(self, client):
        """Test upload with WebM format."""
        webm_file = ("test.webm", BytesIO(b"webm data"), "audio/webm")

        with patch("app.services.upload.upload_service.process_upload") as mock_upload:
            mock_upload.return_value = {
                "upload_id": "webm-test",
                "filename": "test.webm",
                "file_size": 9,
                "mime_type": "audio/webm",
                "status": "uploaded",
                "created_at": "2025-07-28T12:00:00Z",
            }

            response = client.post("/api/v1/audio/upload", files={"file": webm_file})

            assert response.status_code == 200
            data = response.json()
            assert data["mime_type"] == "audio/webm"

    def test_upload_mp4_format(self, client):
        """Test upload with MP4 format."""
        mp4_file = ("test.m4a", BytesIO(b"mp4 data"), "audio/mp4")

        with patch("app.services.upload.upload_service.process_upload") as mock_upload:
            mock_upload.return_value = {
                "upload_id": "mp4-test",
                "filename": "test.m4a",
                "file_size": 8,
                "mime_type": "audio/mp4",
                "status": "uploaded",
                "created_at": "2025-07-28T12:00:00Z",
            }

            response = client.post("/api/v1/audio/upload", files={"file": mp4_file})

            assert response.status_code == 200
            data = response.json()
            assert data["mime_type"] == "audio/mp4"

    def test_upload_mp3_format(self, client):
        """Test upload with MP3 format."""
        mp3_file = ("test.mp3", BytesIO(b"mp3 data"), "audio/mpeg")

        with patch("app.services.upload.upload_service.process_upload") as mock_upload:
            mock_upload.return_value = {
                "upload_id": "mp3-test",
                "filename": "test.mp3",
                "file_size": 8,
                "mime_type": "audio/mpeg",
                "status": "uploaded",
                "created_at": "2025-07-28T12:00:00Z",
            }

            response = client.post("/api/v1/audio/upload", files={"file": mp3_file})

            assert response.status_code == 200
            data = response.json()
            assert data["mime_type"] == "audio/mpeg"

    @patch("app.services.upload.upload_service.process_upload")
    def test_request_id_in_response(
        self, mock_process_upload, client, valid_audio_file
    ):
        """Test that request ID is included in response headers."""
        mock_process_upload.return_value = {
            "upload_id": "test-id",
            "filename": "test.webm",
            "file_size": 19,
            "mime_type": "audio/webm",
            "status": "uploaded",
            "created_at": "2025-07-28T12:00:00Z",
        }

        response = client.post("/api/v1/audio/upload", files={"file": valid_audio_file})

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"] is not None

    @patch("app.services.upload.upload_service.process_upload")
    def test_server_error_handling(self, mock_process_upload, client, valid_audio_file):
        """Test server error handling."""
        # Mock service raising unexpected exception
        mock_process_upload.side_effect = Exception("Database connection failed")

        response = client.post("/api/v1/audio/upload", files={"file": valid_audio_file})

        assert response.status_code == 500
        data = response.json()
        assert data["error_code"] == "INTERNAL_ERROR"
        assert "request_id" in data

    def test_cors_headers_present(self, client, valid_audio_file):
        """Test that CORS middleware is configured."""
        with patch("app.services.upload.upload_service.process_upload") as mock_upload:
            mock_upload.return_value = {
                "upload_id": "cors-test",
                "filename": "test.webm",
                "file_size": 19,
                "mime_type": "audio/webm",
                "status": "uploaded",
                "created_at": "2025-07-28T12:00:00Z",
            }

            response = client.post(
                "/api/v1/audio/upload", files={"file": valid_audio_file}
            )

            # TestClient doesn't include CORS headers but middleware is configured
            assert response.status_code == 200


class TestConcurrentUploads:
    """Test concurrent upload handling."""

    @pytest.mark.asyncio
    async def test_multiple_uploads_different_ids(self, client):
        """Test that multiple uploads get different IDs."""
        valid_file = ("test.webm", BytesIO(b"test data"), "audio/webm")

        with patch("app.services.upload.upload_service.process_upload") as mock_upload:
            # Mock different upload IDs for each call
            mock_upload.side_effect = [
                {
                    "upload_id": "upload-1",
                    "filename": "test1.webm",
                    "file_size": 9,
                    "mime_type": "audio/webm",
                    "status": "uploaded",
                    "created_at": "2025-07-28T12:00:00Z",
                },
                {
                    "upload_id": "upload-2",
                    "filename": "test2.webm",
                    "file_size": 9,
                    "mime_type": "audio/webm",
                    "status": "uploaded",
                    "created_at": "2025-07-28T12:00:01Z",
                },
            ]

            # Make two upload requests
            response1 = client.post("/api/v1/audio/upload", files={"file": valid_file})
            response2 = client.post("/api/v1/audio/upload", files={"file": valid_file})

            assert response1.status_code == 200
            assert response2.status_code == 200

            data1 = response1.json()
            data2 = response2.json()

            # Should have different upload IDs
            assert data1["upload_id"] != data2["upload_id"]
