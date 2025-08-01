"""Tests for the markdown formatter service."""

import pytest
from datetime import datetime
from unittest.mock import patch

from app.services.markdown_formatter import MarkdownFormatter, markdown_formatter


class TestMarkdownFormatter:
    """Test cases for the MarkdownFormatter class."""

    def setup_method(self):
        """Setup test instance."""
        self.formatter = MarkdownFormatter()

    def test_format_transcription_basic(self):
        """Test basic transcription formatting with all inputs."""
        transcription = "This is a test transcription of a voice note."
        summary = "• Key point 1\n• Key point 2"
        keywords = ["test", "voice note", "transcription"]
        metadata = {"duration": 60, "language": "en"}
        upload_id = "test-upload-123"

        result = self.formatter.format_transcription(
            transcription_text=transcription,
            summary=summary,
            keywords=keywords,
            metadata=metadata,
            upload_id=upload_id,
        )

        # Check YAML frontmatter structure
        lines = result.split("\n")
        assert lines[0] == "---"
        
        # Find the end of frontmatter
        frontmatter_end = lines[1:].index("---") + 1
        frontmatter_lines = lines[1:frontmatter_end]
        
        # Check required frontmatter fields
        frontmatter_content = "\n".join(frontmatter_lines)
        assert "type: voice-note" in frontmatter_content
        assert "created:" in frontmatter_content
        assert "processed_by: dialtone" in frontmatter_content
        assert "upload_id: test-upload-123" in frontmatter_content
        assert "duration: 60" in frontmatter_content
        assert "language: en" in frontmatter_content
        assert "tags:" in frontmatter_content
        
        # Check content sections
        content_after_frontmatter = "\n".join(lines[frontmatter_end + 1:])
        assert "## Summary" in content_after_frontmatter
        assert "## Transcription" in content_after_frontmatter
        assert transcription in content_after_frontmatter
        assert summary in content_after_frontmatter

    def test_format_transcription_minimal(self):
        """Test formatting with only transcription text."""
        transcription = "Simple transcription text."
        
        result = self.formatter.format_transcription(transcription_text=transcription)
        
        # Check basic structure
        assert result.startswith("---\n")
        assert "type: voice-note" in result
        assert "created:" in result
        assert "processed_by: dialtone" in result
        assert "## Transcription" in result
        assert transcription in result
        
        # Should not have summary section
        assert "## Summary" not in result

    def test_format_transcription_empty_content(self):
        """Test handling of empty transcription text."""
        result = self.formatter.format_transcription(transcription_text="")
        
        assert "No transcription content available." in result
        assert "type: voice-note" in result

    def test_format_transcription_whitespace_only(self):
        """Test handling of whitespace-only transcription."""
        result = self.formatter.format_transcription(transcription_text="   \n\t  ")
        
        assert "No transcription content available." in result

    def test_yaml_frontmatter_special_characters(self):
        """Test YAML frontmatter with special characters in values."""
        transcription = "Test content"
        metadata = {
            "filename": "file:with:colons.mp3",
            "description": "Multi-line\ndescription with\nbreaks"
        }
        
        result = self.formatter.format_transcription(
            transcription_text=transcription,
            metadata=metadata
        )
        
        # Values with special characters should be quoted
        assert 'filename: "file:with:colons.mp3"' in result
        assert 'description: "Multi-line\ndescription with\nbreaks"' in result

    def test_keyword_cleaning_basic(self):
        """Test basic keyword cleaning functionality."""
        keywords = ["test keyword", "voice-note", "AI transcription"]
        
        cleaned = self.formatter._clean_keywords_for_obsidian(keywords)
        
        assert "test-keyword" in cleaned
        assert "voice-note" in cleaned
        assert "ai-transcription" in cleaned

    def test_keyword_cleaning_special_characters(self):
        """Test keyword cleaning with various special characters."""
        keywords = [
            "hello, world!",
            "question?",
            "statement.",
            "semicolon;here",
            "colon:there",
            "multiple  spaces",
            "under_score",
            "mixed-chars_and spaces!"
        ]
        
        cleaned = self.formatter._clean_keywords_for_obsidian(keywords)
        
        expected = [
            "hello-world",
            "question",
            "statement",
            "semicolonhere",
            "colonthere",
            "multiple-spaces",
            "under-score",
            "mixed-chars-and-spaces"
        ]
        
        for expected_keyword in expected:
            assert expected_keyword in cleaned

    def test_keyword_cleaning_length_constraints(self):
        """Test keyword length constraints."""
        keywords = [
            "a",  # Too short
            "ok",  # Minimum length
            "perfect_length_keyword",  # Good length
            "this_is_a_very_long_keyword_that_exceeds_the_thirty_character_limit",  # Too long
            "",  # Empty
            "   ",  # Whitespace only
        ]
        
        cleaned = self.formatter._clean_keywords_for_obsidian(keywords)
        
        assert "a" not in cleaned  # Too short
        assert "ok" in cleaned  # Minimum length
        assert "perfect-length-keyword" in cleaned  # Good length
        assert len([k for k in cleaned if len(k) > 30]) == 0  # No long keywords

    def test_keyword_cleaning_duplicates(self):
        """Test removal of duplicate keywords."""
        keywords = ["test", "TEST", "Test", "test keyword", "test-keyword"]
        
        cleaned = self.formatter._clean_keywords_for_obsidian(keywords)
        
        # Should only have unique lowercase versions
        assert cleaned.count("test") == 1
        assert cleaned.count("test-keyword") == 1

    def test_keyword_cleaning_empty_input(self):
        """Test keyword cleaning with empty input."""
        assert self.formatter._clean_keywords_for_obsidian([]) == []
        assert self.formatter._clean_keywords_for_obsidian(None) == []

    def test_keyword_cleaning_non_string_input(self):
        """Test keyword cleaning with non-string inputs."""
        keywords = ["valid", 123, None, "", "another_valid"]
        
        cleaned = self.formatter._clean_keywords_for_obsidian(keywords)
        
        assert "valid" in cleaned
        assert "another-valid" in cleaned
        assert len(cleaned) == 2  # Only string keywords processed

    def test_filename_generation_basic(self):
        """Test basic filename generation."""
        upload_id = "test-upload-12345678"
        timestamp = datetime(2024, 1, 15, 14, 30, 45)
        
        filename = self.formatter.format_for_obsidian_filename(upload_id, timestamp)
        
        assert filename == "voice-note_2024-01-15_14-30_test-upl"
        assert len(filename) <= 50  # Reasonable length

    def test_filename_generation_default_timestamp(self):
        """Test filename generation with default timestamp."""
        upload_id = "test-upload-123"
        
        with patch('app.services.markdown_formatter.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, 14, 30, 45)
            
            filename = self.formatter.format_for_obsidian_filename(upload_id)
            
            assert filename.startswith("voice-note_2024-01-15_14-30")
            assert "test-upl" in filename

    def test_filename_generation_special_characters(self):
        """Test filename generation with special characters in upload_id."""
        upload_id = "test@upload#with$special%chars"
        timestamp = datetime(2024, 1, 15, 14, 30, 45)
        
        filename = self.formatter.format_for_obsidian_filename(upload_id, timestamp)
        
        # Should only contain safe characters
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        assert all(c in safe_chars for c in filename)

    def test_format_transcription_tags_in_frontmatter(self):
        """Test that keywords appear as tags in YAML frontmatter."""
        transcription = "Test content"
        keywords = ["keyword1", "keyword 2", "keyword-3"]
        
        result = self.formatter.format_transcription(
            transcription_text=transcription,
            keywords=keywords
        )
        
        # Check tags section in frontmatter
        assert "tags:" in result
        assert "- keyword1" in result
        assert "- keyword-2" in result
        assert "- keyword-3" in result

    def test_format_transcription_no_tags_when_empty_keywords(self):
        """Test that no tags section is created when keywords are empty."""
        transcription = "Test content"
        
        result = self.formatter.format_transcription(
            transcription_text=transcription,
            keywords=[]
        )
        
        assert "tags:" not in result

    def test_metadata_merge_no_conflicts(self):
        """Test metadata merging without conflicts."""
        transcription = "Test content"
        metadata = {"custom_field": "custom_value", "duration": 120}
        
        result = self.formatter.format_transcription(
            transcription_text=transcription,
            metadata=metadata
        )
        
        assert "custom_field: custom_value" in result
        assert "duration: 120" in result

    def test_metadata_merge_with_conflicts(self):
        """Test that existing frontmatter fields are not overwritten by metadata."""
        transcription = "Test content"
        metadata = {"type": "custom-type", "created": "custom-date"}  # Conflicts
        
        result = self.formatter.format_transcription(
            transcription_text=transcription,
            metadata=metadata
        )
        
        # Original values should be preserved
        assert "type: voice-note" in result
        assert "type: custom-type" not in result
        assert "created: custom-date" not in result

    def test_global_instance_available(self):
        """Test that global markdown_formatter instance is available."""
        assert markdown_formatter is not None
        assert isinstance(markdown_formatter, MarkdownFormatter)

    @patch('app.services.markdown_formatter.logger')
    def test_logging_info_called(self, mock_logger):
        """Test that info logging is called during formatting."""
        transcription = "Test content"
        upload_id = "test-123"
        
        self.formatter.format_transcription(
            transcription_text=transcription,
            upload_id=upload_id
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "Formatted transcription for Obsidian" in call_args[0][0]

    @patch('app.services.markdown_formatter.logger')
    def test_logging_warning_empty_transcription(self, mock_logger):
        """Test that warning is logged for empty transcription."""
        self.formatter.format_transcription(transcription_text="")
        
        mock_logger.warning.assert_called_once_with(
            "Empty transcription text provided to formatter"
        )

    def test_format_transcription_content_structure(self):
        """Test the overall structure of formatted content."""
        transcription = "This is the transcription content."
        summary = "This is the summary."
        
        result = self.formatter.format_transcription(
            transcription_text=transcription,
            summary=summary
        )
        
        lines = result.split("\n")
        
        # Should start with YAML frontmatter
        assert lines[0] == "---"
        
        # Find structure markers
        frontmatter_end = None
        summary_start = None
        transcription_start = None
        
        for i, line in enumerate(lines):
            if line == "---" and frontmatter_end is None and i > 0:
                frontmatter_end = i
            elif line == "## Summary":
                summary_start = i
            elif line == "## Transcription":
                transcription_start = i
        
        # Verify structure order
        assert frontmatter_end is not None
        assert summary_start is not None
        assert transcription_start is not None
        assert frontmatter_end < summary_start < transcription_start

    def test_integration_with_real_data_simulation(self):
        """Test with realistic data that simulates actual usage."""
        transcription = """
        Today I had a meeting with the client about the new project requirements. 
        They want us to focus on user experience and make sure the interface is 
        intuitive. We discussed the timeline and agreed on a two-week sprint to 
        deliver the first prototype.
        """.strip()
        
        summary = """
        • Client meeting about new project
        • Focus on user experience and intuitive interface
        • Two-week sprint timeline agreed
        • First prototype to be delivered
        """
        
        keywords = [
            "client meeting",
            "project requirements", 
            "user experience",
            "intuitive interface",
            "timeline",
            "two-week sprint",
            "prototype"
        ]
        
        metadata = {
            "duration": 185,
            "language": "en",
            "audio_format": "webm",
            "file_size": 2048576
        }
        
        upload_id = "upload_2024_01_15_14_30_45_abc123"
        
        result = self.formatter.format_transcription(
            transcription_text=transcription,
            summary=summary,
            keywords=keywords,
            metadata=metadata,
            upload_id=upload_id
        )
        
        # Verify all components are present and well-formed
        assert result.startswith("---\n")
        assert "type: voice-note" in result
        assert upload_id in result
        assert "## Summary" in result
        assert "## Transcription" in result
        assert transcription in result
        assert summary.strip() in result
        
        # Check that keywords are properly formatted
        assert "tags:" in result
        assert "- client-meeting" in result
        assert "- user-experience" in result
        
        # Verify metadata is included
        assert "duration: 185" in result
        assert "language: en" in result