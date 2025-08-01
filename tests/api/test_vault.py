"""Tests for vault API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.core.exceptions import VaultAccessError, VaultWriteError
from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestVaultAPI:
    """Test vault API endpoints."""

    def test_save_to_vault_success(self, client):
        """Test successful save to vault."""
        with patch("app.api.vault.vault_service") as mock_service:
            mock_service.save_transcription_to_vault = AsyncMock(
                return_value={
                    "success": True,
                    "file_path": "voice-note_2024-08-01_14-30_test123.md",
                    "filename": "voice-note_2024-08-01_14-30_test123.md",
                    "full_path": "/vault/voice-note_2024-08-01_14-30_test123.md",
                }
            )

            response = client.post(
                "/api/v1/vault/save",
                json={
                    "upload_id": "test123",
                    "transcription": "This is a test transcription.",
                    "summary": "Test summary",
                    "keywords": ["test", "vault"],
                },
            )

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["success"] is True
            assert "test123" in data["filename"]
            assert data["file_path"] == "voice-note_2024-08-01_14-30_test123.md"

    def test_save_to_vault_access_error(self, client):
        """Test vault access error handling."""
        with patch("app.api.vault.vault_service") as mock_service:
            mock_service.save_transcription_to_vault = AsyncMock(
                side_effect=VaultAccessError("No write permission")
            )

            response = client.post(
                "/api/v1/vault/save",
                json={
                    "upload_id": "test123",
                    "transcription": "Test",
                },
            )

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert data["error_code"] == "VAULT_ACCESS_ERROR"

    def test_save_to_vault_write_error(self, client):
        """Test vault write error handling."""
        with patch("app.api.vault.vault_service") as mock_service:
            mock_service.save_transcription_to_vault = AsyncMock(
                side_effect=VaultWriteError("Disk full")
            )

            response = client.post(
                "/api/v1/vault/save",
                json={
                    "upload_id": "test123",
                    "transcription": "Test",
                },
            )

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert data["error_code"] == "VAULT_WRITE_ERROR"

    def test_save_to_vault_validation_error(self, client):
        """Test request validation."""
        response = client.post(
            "/api/v1/vault/save",
            json={
                # Missing required fields
                "summary": "Test summary",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert "error_code" in data
        assert data["error_code"] == "VALIDATION_ERROR"

    def test_save_minimal_request(self, client):
        """Test save with minimal required fields."""
        with patch("app.api.vault.vault_service") as mock_service:
            mock_service.save_transcription_to_vault = AsyncMock(
                return_value={
                    "success": True,
                    "file_path": "voice-note_2024-08-01_14-30_test123.md",
                    "filename": "voice-note_2024-08-01_14-30_test123.md",
                    "full_path": "/vault/voice-note_2024-08-01_14-30_test123.md",
                }
            )

            response = client.post(
                "/api/v1/vault/save",
                json={
                    "upload_id": "test123",
                    "transcription": "Minimal test",
                },
            )

            assert response.status_code == status.HTTP_201_CREATED

            # Verify service was called without optional fields
            mock_service.save_transcription_to_vault.assert_called_once_with(
                upload_id="test123",
                transcription="Minimal test",
                summary=None,
                keywords=None,
                metadata=None,
            )

    def test_save_with_all_fields(self, client):
        """Test save with all optional fields."""
        with patch("app.api.vault.vault_service") as mock_service:
            mock_service.save_transcription_to_vault = AsyncMock(
                return_value={
                    "success": True,
                    "file_path": "voice-note_2024-08-01_14-30_test123.md",
                    "filename": "voice-note_2024-08-01_14-30_test123.md",
                    "full_path": "/vault/voice-note_2024-08-01_14-30_test123.md",
                }
            )

            response = client.post(
                "/api/v1/vault/save",
                json={
                    "upload_id": "test123",
                    "transcription": "Full test transcription",
                    "summary": "- This is a summary\n- With multiple points",
                    "keywords": ["test", "vault", "api"],
                    "metadata": {"source": "test", "confidence": 0.98, "duration": 120},
                },
            )

            assert response.status_code == status.HTTP_201_CREATED

            # Verify service was called with all fields
            mock_service.save_transcription_to_vault.assert_called_once_with(
                upload_id="test123",
                transcription="Full test transcription",
                summary="- This is a summary\n- With multiple points",
                keywords=["test", "vault", "api"],
                metadata={"source": "test", "confidence": 0.98, "duration": 120},
            )

    def test_save_keywords_limit(self, client):
        """Test keywords field length validation."""
        response = client.post(
            "/api/v1/vault/save",
            json={
                "upload_id": "test123",
                "transcription": "Test",
                "keywords": ["kw" + str(i) for i in range(15)],  # Too many keywords
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_save_empty_transcription(self, client):
        """Test save with empty transcription."""
        with patch("app.api.vault.vault_service") as mock_service:
            mock_service.save_transcription_to_vault = AsyncMock(
                return_value={
                    "success": True,
                    "file_path": "voice-note_2024-08-01_14-30_test123.md",
                    "filename": "voice-note_2024-08-01_14-30_test123.md",
                    "full_path": "/vault/voice-note_2024-08-01_14-30_test123.md",
                }
            )

            response = client.post(
                "/api/v1/vault/save",
                json={
                    "upload_id": "test123",
                    "transcription": "",  # Empty transcription
                },
            )

            assert response.status_code == status.HTTP_201_CREATED

    def test_save_unexpected_error(self, client):
        """Test handling of unexpected errors."""
        with patch("app.api.vault.vault_service") as mock_service:
            mock_service.save_transcription_to_vault = AsyncMock(
                side_effect=Exception("Unexpected error")
            )

            response = client.post(
                "/api/v1/vault/save",
                json={
                    "upload_id": "test123",
                    "transcription": "Test",
                },
            )

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert "An unexpected error occurred" in data["error"]

    def test_save_large_transcription(self, client):
        """Test save with large transcription content."""
        with patch("app.api.vault.vault_service") as mock_service:
            mock_service.save_transcription_to_vault = AsyncMock(
                return_value={
                    "success": True,
                    "file_path": "voice-note_2024-08-01_14-30_test123.md",
                    "filename": "voice-note_2024-08-01_14-30_test123.md",
                    "full_path": "/vault/voice-note_2024-08-01_14-30_test123.md",
                }
            )

            # Create large transcription (10KB)
            large_transcription = "This is a test sentence. " * 400

            response = client.post(
                "/api/v1/vault/save",
                json={
                    "upload_id": "test123",
                    "transcription": large_transcription,
                },
            )

            assert response.status_code == status.HTTP_201_CREATED

    def test_invalid_upload_id_format(self, client):
        """Test with various upload ID formats."""
        with patch("app.api.vault.vault_service") as mock_service:
            mock_service.save_transcription_to_vault = AsyncMock(
                return_value={
                    "success": True,
                    "file_path": "voice-note_2024-08-01_14-30_test123.md",
                    "filename": "voice-note_2024-08-01_14-30_test123.md",
                    "full_path": "/vault/voice-note_2024-08-01_14-30_test123.md",
                }
            )

            # Test with different upload ID formats
            test_ids = ["123", "abc-def-ghi", "upload_123_test", "UPPERCASE123"]

            for upload_id in test_ids:
                response = client.post(
                    "/api/v1/vault/save",
                    json={
                        "upload_id": upload_id,
                        "transcription": f"Test for {upload_id}",
                    },
                )
                assert response.status_code == status.HTTP_201_CREATED
