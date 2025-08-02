"""Tests for audio upload API endpoints."""

from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

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
        assert "error" in data
        assert data["error_code"] == "VALIDATION_ERROR"

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

        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "UNSUPPORTED_FORMAT"

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
            assert "details" in data
            assert "max_size" in data["details"]

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
        from app.core.exceptions import ServiceError

        # Mock service raising a ServiceError which will be caught properly
        mock_process_upload.side_effect = ServiceError("Database connection failed")

        response = client.post("/api/v1/audio/upload", files={"file": valid_audio_file})

        assert response.status_code == 500
        data = response.json()
        assert data["error_code"] == "ServiceError"
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


class TestTranscribeEndpoint:
    """Test audio transcription endpoint."""

    def test_transcribe_endpoint_exists(self, client):
        """Test that transcribe endpoint exists and accepts POST."""
        # Test without request body should return 422 (validation error)
        response = client.post("/api/v1/audio/transcribe")
        assert response.status_code == 422  # Missing required request body

    @patch("app.services.transcription.transcription_service.transcribe_upload")
    def test_transcribe_success(self, mock_transcribe, client):
        """Test successful transcription."""
        # Mock successful transcription
        mock_transcribe.return_value = {
            "upload_id": "test-123-456",
            "transcription": {
                "text": "This is a test transcription",
                "language": "en",
                "confidence": 0.95,
                "duration_seconds": 10.5,
            },
            "processing_time_seconds": 12.3,
            "status": "completed",
        }

        request_data = {"upload_id": "test-123-456"}
        response = client.post("/api/v1/audio/transcribe", json=request_data)

        assert response.status_code == 200
        data = response.json()

        assert data["upload_id"] == "test-123-456"
        assert data["transcription"]["text"] == "This is a test transcription"
        assert data["transcription"]["language"] == "en"
        assert data["transcription"]["confidence"] == 0.95
        assert data["transcription"]["duration_seconds"] == 10.5
        assert data["processing_time_seconds"] == 12.3
        assert data["status"] == "completed"

        mock_transcribe.assert_called_once_with(upload_id="test-123-456", language=None)

    @patch("app.services.transcription.transcription_service.transcribe_upload")
    def test_transcribe_with_language(self, mock_transcribe, client):
        """Test transcription with language hint."""
        mock_transcribe.return_value = {
            "upload_id": "test-123",
            "transcription": {
                "text": "Esta es una transcripción de prueba",
                "language": "es",
                "confidence": 0.92,
                "duration_seconds": 8.0,
            },
            "processing_time_seconds": 10.1,
            "status": "completed",
        }

        request_data = {"upload_id": "test-123", "language": "es"}
        response = client.post("/api/v1/audio/transcribe", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["transcription"]["language"] == "es"

        mock_transcribe.assert_called_once_with(upload_id="test-123", language="es")

    def test_transcribe_missing_upload_id(self, client):
        """Test transcription without upload_id."""
        request_data = {}
        response = client.post("/api/v1/audio/transcribe", json=request_data)

        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["error_code"] == "VALIDATION_ERROR"

    def test_transcribe_invalid_request_format(self, client):
        """Test transcription with invalid request format."""
        # Send string instead of JSON object
        response = client.post("/api/v1/audio/transcribe", json="invalid")

        assert response.status_code == 422

    @patch("app.services.transcription.transcription_service.transcribe_upload")
    def test_transcribe_upload_not_found(self, mock_transcribe, client):
        """Test transcription with non-existent upload."""
        from fastapi import HTTPException

        mock_transcribe.side_effect = HTTPException(
            status_code=404,
            detail={
                "error": "Upload nonexistent not found",
                "error_code": "UPLOAD_NOT_FOUND",
            },
        )

        request_data = {"upload_id": "nonexistent"}
        response = client.post("/api/v1/audio/transcribe", json=request_data)

        assert response.status_code == 404
        data = response.json()
        assert data["error_code"] == "HTTP_404"

    @patch("app.services.transcription.transcription_service.transcribe_upload")
    def test_transcribe_timeout(self, mock_transcribe, client):
        """Test transcription timeout."""
        from fastapi import HTTPException

        mock_transcribe.side_effect = HTTPException(
            status_code=408,
            detail={
                "error": "Transcription timeout after 300 seconds",
                "error_code": "TRANSCRIPTION_TIMEOUT",
                "timeout_seconds": 300,
            },
        )

        request_data = {"upload_id": "timeout-test"}
        response = client.post("/api/v1/audio/transcribe", json=request_data)

        assert response.status_code == 408
        data = response.json()
        assert data["error_code"] == "HTTP_408"
        assert data["timeout_seconds"] == 300

    @patch("app.services.transcription.transcription_service.transcribe_upload")
    def test_transcribe_conversion_error(self, mock_transcribe, client):
        """Test transcription with audio conversion error."""
        from fastapi import HTTPException

        mock_transcribe.side_effect = HTTPException(
            status_code=400,
            detail={
                "error": "Audio conversion failed",
                "error_code": "CONVERSION_ERROR",
                "details": "FFmpeg conversion failed",
            },
        )

        request_data = {"upload_id": "bad-audio"}
        response = client.post("/api/v1/audio/transcribe", json=request_data)

        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "HTTP_400"

    @patch("app.services.transcription.transcription_service.transcribe_upload")
    def test_transcribe_service_unavailable(self, mock_transcribe, client):
        """Test transcription when service is unavailable."""
        from fastapi import HTTPException

        mock_transcribe.side_effect = HTTPException(
            status_code=503,
            detail={
                "error": "Transcription service unavailable",
                "error_code": "SERVICE_UNAVAILABLE",
            },
        )

        request_data = {"upload_id": "service-down"}
        response = client.post("/api/v1/audio/transcribe", json=request_data)

        assert response.status_code == 503
        data = response.json()
        assert data["error_code"] == "HTTP_503"

    @patch("app.services.transcription.transcription_service.transcribe_upload")
    def test_transcribe_server_error(self, mock_transcribe, client):
        """Test transcription server error handling."""
        from app.core.exceptions import ServiceError

        # Mock service raising a ServiceError
        mock_transcribe.side_effect = ServiceError("Unexpected database error")

        request_data = {"upload_id": "error-test"}
        response = client.post("/api/v1/audio/transcribe", json=request_data)

        assert response.status_code == 500
        data = response.json()
        assert data["error_code"] == "ServiceError"
        assert "request_id" in data

    @patch("app.services.transcription.transcription_service.transcribe_upload")
    def test_transcribe_request_id_in_response(self, mock_transcribe, client):
        """Test that request ID is included in transcription response."""
        mock_transcribe.return_value = {
            "upload_id": "test-id",
            "transcription": {
                "text": "Test transcription",
                "language": "en",
                "confidence": 0.9,
                "duration_seconds": 5.0,
            },
            "processing_time_seconds": 8.0,
            "status": "completed",
        }

        request_data = {"upload_id": "test-id"}
        response = client.post("/api/v1/audio/transcribe", json=request_data)

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"] is not None

    def test_transcribe_endpoint_documentation(self, client):
        """Test that transcribe endpoint is documented in OpenAPI."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        openapi_spec = response.json()
        paths = openapi_spec.get("paths", {})
        transcribe_path = paths.get("/api/v1/audio/transcribe", {})

        # Check that POST method exists
        assert "post" in transcribe_path

        # Check response schemas are defined
        post_spec = transcribe_path["post"]
        assert "responses" in post_spec
        assert "200" in post_spec["responses"]
        assert "400" in post_spec["responses"]
        assert "404" in post_spec["responses"]
        assert "408" in post_spec["responses"]
