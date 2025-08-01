"""Tests for keyword extraction integration."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.services.markdown_formatter import markdown_formatter
from app.services.transcription import transcription_service


class TestKeywordIntegration:
    """Test keyword extraction integration into transcription pipeline."""

    @pytest.fixture
    def mock_transcription_result(self):
        """Mock Whisper transcription result."""
        return {
            "text": "This is a test transcription about project management and team collaboration.",
            "language": "en",
            "segments": [{"avg_logprob": -0.2, "text": "This is a test transcription"}],
        }

    @pytest.fixture
    def mock_keywords(self):
        """Mock extracted keywords."""
        return ["project-management", "team", "collaboration", "test", "transcription"]

    @patch("app.services.transcription.settings")
    @pytest.mark.asyncio
    async def test_keyword_extraction_enabled(
        self, mock_settings, mock_transcription_result, mock_keywords, tmp_path
    ):
        """Test keyword extraction when enabled."""
        # Setup mock file system
        upload_dir = tmp_path / "test_upload"
        upload_dir.mkdir()
        audio_file = upload_dir / "test.webm"
        audio_file.write_text("mock audio content")

        mock_settings.upload_dir = tmp_path
        mock_settings.keyword_extraction_enabled = True
        mock_settings.keyword_max_count = 5

        with patch.multiple(
            "app.services.transcription",
            whisper_manager=Mock(
                is_loaded=True,
                is_loading=False,
                transcribe=AsyncMock(return_value=mock_transcription_result),
            ),
            audio_converter=Mock(
                get_audio_info=AsyncMock(
                    return_value={
                        "duration": 10.0,
                        "format": "webm",
                        "sample_rate": 16000,
                        "channels": 1,
                    }
                ),
                is_conversion_needed=Mock(return_value=False),
            ),
            ollama_service=Mock(
                health_check=AsyncMock(return_value=True),
                extract_keywords=AsyncMock(return_value=mock_keywords),
            ),
        ):
            result = await transcription_service.transcribe_upload(
                upload_id="test_upload",
                language="en",
                include_summary=False,
                max_summary_words=150,
            )

            # Verify keywords are included in response
            assert "keywords" in result
            assert result["keywords"] == mock_keywords
            assert "keyword_processing_time" in result
            assert isinstance(result["keyword_processing_time"], float)
            assert result["keyword_processing_time"] >= 0

    @patch("app.services.transcription.settings")
    @pytest.mark.asyncio
    async def test_keyword_extraction_disabled(
        self, mock_settings, mock_transcription_result, tmp_path
    ):
        """Test transcription when keyword extraction is disabled."""
        # Setup mock file system
        upload_dir = tmp_path / "test_upload"
        upload_dir.mkdir()
        audio_file = upload_dir / "test.webm"
        audio_file.write_text("mock audio content")

        mock_settings.upload_dir = tmp_path
        mock_settings.keyword_extraction_enabled = False

        with patch.multiple(
            "app.services.transcription",
            whisper_manager=Mock(
                is_loaded=True,
                is_loading=False,
                transcribe=AsyncMock(return_value=mock_transcription_result),
            ),
            audio_converter=Mock(
                get_audio_info=AsyncMock(
                    return_value={
                        "duration": 10.0,
                        "format": "webm",
                        "sample_rate": 16000,
                        "channels": 1,
                    }
                ),
                is_conversion_needed=Mock(return_value=False),
            ),
        ):
            result = await transcription_service.transcribe_upload(
                upload_id="test_upload",
                language="en",
                include_summary=False,
                max_summary_words=150,
            )

            # Verify keywords are not included when disabled
            assert "keywords" not in result
            assert "keyword_processing_time" not in result

    def test_markdown_formatting_with_keywords(self):
        """Test markdown formatter includes keywords in frontmatter."""
        transcription_text = "This is a test transcription about project management."
        summary = "- Project management discussion\n- Key points identified"
        keywords = ["project-management", "discussion", "key-points"]
        upload_id = "test_upload_123"

        result = markdown_formatter.format_transcription(
            transcription_text=transcription_text,
            summary=summary,
            keywords=keywords,
            upload_id=upload_id,
        )

        # Verify YAML frontmatter structure
        assert result.startswith("---")
        assert "type: voice-note" in result
        assert "processed_by: dialtone" in result
        assert f"upload_id: {upload_id}" in result
        assert "tags:" in result
        assert "- project-management" in result
        assert "- discussion" in result
        assert "- key-points" in result

        # Verify content sections
        assert "## Summary" in result
        assert "## Transcription" in result
        assert transcription_text in result
        assert summary in result

    def test_markdown_formatting_without_keywords(self):
        """Test markdown formatter works without keywords."""
        transcription_text = "This is a test transcription."
        upload_id = "test_upload_123"

        result = markdown_formatter.format_transcription(
            transcription_text=transcription_text,
            keywords=None,
            upload_id=upload_id,
        )

        # Verify YAML frontmatter structure without tags
        assert result.startswith("---")
        assert "type: voice-note" in result
        assert "processed_by: dialtone" in result
        assert f"upload_id: {upload_id}" in result
        assert "tags:" not in result

        # Verify content sections
        assert "## Transcription" in result
        assert transcription_text in result

    def test_keyword_cleaning_for_obsidian(self):
        """Test keyword cleaning for Obsidian compatibility."""
        test_keywords = [
            "Project Management",  # Should become "project-management"
            "API Design!",  # Should become "api-design"
            "team_collaboration",  # Should become "team-collaboration"
            "database,queries",  # Should become "database-queries"
            "a",  # Too short, should be filtered
            "this-is-a-very-long-keyword-that-exceeds-the-limit",  # Too long
            "",  # Empty, should be filtered
            "valid-keyword",  # Should remain as-is
        ]

        cleaned = markdown_formatter._clean_keywords_for_obsidian(test_keywords)

        expected = [
            "project-management",
            "api-design",
            "team-collaboration",
            "database-queries",
            "valid-keyword",
        ]

        assert cleaned == expected

    def test_obsidian_filename_generation(self):
        """Test Obsidian-safe filename generation."""
        from datetime import datetime

        upload_id = "upload_abc123def456"
        test_timestamp = datetime(2024, 1, 15, 14, 30, 45)

        filename = markdown_formatter.format_for_obsidian_filename(
            upload_id, test_timestamp
        )

        assert filename == "voice-note_2024-01-15_14-30_upload_a"
        assert len(filename) <= 50  # Reasonable filename length
        assert all(c.isalnum() or c in "-_" for c in filename)  # Safe characters only
