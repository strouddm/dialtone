"""Tests for vault service."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    VaultAccessError,
    VaultConfigurationError,
    VaultWriteError,
)
from app.services.vault import VaultService


@pytest.fixture
def mock_settings(tmp_path):
    """Mock settings with temp vault path."""
    with patch("app.services.vault.settings") as mock:
        mock.obsidian_vault_path = tmp_path / "test_vault"
        yield mock


@pytest.fixture
def vault_service(mock_settings):
    """Create vault service with mocked settings."""
    return VaultService()


class TestVaultService:
    """Test vault service functionality."""

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_save_transcription_success(self, vault_service, tmp_path):
        """Test successful save to vault."""
        # Create vault directory
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()

        result = await vault_service.save_transcription_to_vault(
            upload_id="test123",
            transcription="This is a test transcription.",
            summary="- Test summary point",
            keywords=["test", "vault"],
        )

        assert result["success"] is True
        assert "test123" in result["filename"]
        assert result["filename"].endswith(".md")

        # Verify file was created
        saved_file = vault_path / result["filename"]
        assert saved_file.exists()

        # Verify content
        content = saved_file.read_text()
        assert "This is a test transcription." in content
        assert "- Test summary point" in content
        assert "tags:" in content

    @pytest.mark.asyncio
    async def test_vault_not_accessible(self, mock_settings):
        """Test handling of inaccessible vault."""
        # Set vault path to non-existent nested directory with no permissions
        mock_settings.obsidian_vault_path = Path("/root/no_access/vault")

        service = VaultService()

        with pytest.raises(VaultAccessError) as exc_info:
            await service.save_transcription_to_vault(
                upload_id="test",
                transcription="Test",
            )

        assert "Failed to validate vault access" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handle_duplicate_filename(self, vault_service, tmp_path):
        """Test duplicate filename handling."""
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()

        # Save first file
        result1 = await vault_service.save_transcription_to_vault(
            upload_id="duplicate",
            transcription="First file",
        )

        # Mock same filename generation
        with patch.object(
            vault_service, "_generate_filename", return_value=result1["filename"]
        ):
            result2 = await vault_service.save_transcription_to_vault(
                upload_id="duplicate",
                transcription="Second file",
            )

        # Should have different filenames
        assert result1["filename"] != result2["filename"]
        assert "_001" in result2["filename"]

        # Both files should exist
        assert (vault_path / result1["filename"]).exists()
        assert (vault_path / result2["filename"]).exists()

    @pytest.mark.asyncio
    async def test_atomic_write_failure(self, vault_service, tmp_path):
        """Test handling of write failures."""
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()

        # Mock vault access to succeed but atomic write to fail
        with patch.object(vault_service, "_validate_vault_access", return_value=None):
            with patch.object(
                vault_service,
                "_atomic_write",
                side_effect=VaultWriteError("Failed to save file to vault"),
            ):
                with pytest.raises(VaultWriteError) as exc_info:
                    await vault_service.save_transcription_to_vault(
                        upload_id="test",
                        transcription="Test content",
                    )

        assert "Failed to save file to vault" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_vault_status(self, vault_service, tmp_path):
        """Test vault status reporting."""
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()

        status = await vault_service.get_vault_status()

        assert status["accessible"] is True
        assert status["writable"] is True
        assert "free_space_gb" in status
        assert "total_space_gb" in status

    @pytest.mark.asyncio
    async def test_filename_generation(self, vault_service):
        """Test filename generation."""
        filename = vault_service._generate_filename("abc123def456")

        assert filename.startswith("voice-note_")
        assert "abc123de" in filename  # First 8 chars of upload_id
        assert filename.endswith(".md")

    @pytest.mark.asyncio
    async def test_no_vault_path_configured(self):
        """Test error when vault path not configured."""
        with patch("app.services.vault.settings") as mock_settings:
            mock_settings.obsidian_vault_path = None

            with pytest.raises(VaultConfigurationError) as exc_info:
                VaultService()

            assert "Vault path not configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_duplicate_filename_limit(self, vault_service, tmp_path):
        """Test that duplicate filename handling has a reasonable limit."""
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()

        base_filename = "test-file.md"

        # Create many files with same base name
        for i in range(5):
            filename = base_filename if i == 0 else f"test-file_{i:03d}.md"
            (vault_path / filename).touch()

        # Mock to always return the same base filename
        with patch.object(
            vault_service, "_generate_filename", return_value=base_filename
        ):
            result = await vault_service.save_transcription_to_vault(
                upload_id="test",
                transcription="Test content",
            )

            # Should generate test-file_005.md
            assert "_005" in result["filename"]

    @pytest.mark.asyncio
    async def test_save_with_metadata(self, vault_service, tmp_path):
        """Test saving with additional metadata."""
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()

        metadata = {"source": "test", "confidence": 0.95, "language": "en"}

        result = await vault_service.save_transcription_to_vault(
            upload_id="test123",
            transcription="Test transcription",
            metadata=metadata,
        )

        # Verify file was created
        saved_file = vault_path / result["filename"]
        content = saved_file.read_text()

        # Metadata should be included in frontmatter
        assert "source: test" in content
        assert "confidence: 0.95" in content
        assert "language: en" in content

    @pytest.mark.asyncio
    async def test_empty_transcription_handling(self, vault_service, tmp_path):
        """Test handling of empty transcription."""
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()

        result = await vault_service.save_transcription_to_vault(
            upload_id="test123",
            transcription="",  # Empty transcription
        )

        # Should still create file with fallback content
        saved_file = vault_path / result["filename"]
        content = saved_file.read_text()

        # MarkdownFormatter should handle empty content
        assert "## Transcription" in content
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_vault_creation(self, mock_settings, tmp_path):
        """Test automatic vault directory creation."""
        # Set vault path to non-existent directory
        vault_path = tmp_path / "new_vault"
        mock_settings.obsidian_vault_path = vault_path

        service = VaultService()

        # Vault directory should be created automatically
        result = await service.save_transcription_to_vault(
            upload_id="test",
            transcription="Test content",
        )

        assert vault_path.exists()
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_vault_status_error_handling(self, vault_service):
        """Test vault status error handling."""
        # Mock vault path to trigger error
        with patch.object(
            vault_service, "_validate_vault_access", side_effect=Exception("Test error")
        ):
            status = await vault_service.get_vault_status()

            assert status["accessible"] is False
            assert "error" in status
            assert status["writable"] is False
