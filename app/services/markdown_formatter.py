"""Markdown formatting service for Obsidian integration."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MarkdownFormatter:
    """Service for formatting transcriptions into Obsidian-compatible markdown."""

    def format_transcription(
        self,
        transcription_text: str,
        summary: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        upload_id: Optional[str] = None,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """
        Format transcription with title, date, and tags for Obsidian.

        Args:
            transcription_text: The main transcription content (for separate transcript file)
            summary: AI-generated summary (main content)
            keywords: Optional list of extracted keywords
            metadata: Optional additional metadata to include
            upload_id: Optional upload identifier
            title: Generated title for the note
            tags: Optional list of tags (max 3)

        Returns:
            str: Formatted markdown with title, date, tags, and summary only
        """
        # Use provided title or create a fallback, make it lowercase
        note_title = (title or "voice note").lower()

        # Format the date
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Build the content with title and date
        content_parts = [f"# {note_title}", f"date: {current_date}"]

        # Add tags if provided (max 3)
        if tags and len(tags) > 0:
            # Limit to 3 tags and format with # prefix
            tag_list = tags[:3]
            formatted_tags = [f"#{tag.lower().replace(' ', '-')}" for tag in tag_list]
            content_parts.append(f"tags: {' '.join(formatted_tags)}")

        content_parts.append("")

        # Add the summary as the main content (no section header)
        if summary and summary.strip():
            content_parts.append(summary.strip())
        else:
            content_parts.append("No summary available.")

        result = "\n".join(content_parts)

        logger.info(
            "Formatted note for Obsidian",
            extra={
                "upload_id": upload_id,
                "title": note_title,
                "has_summary": summary is not None,
                "content_length": len(result),
            },
        )

        return result

    def format_transcript(
        self,
        transcription_text: str,
        title: Optional[str] = None,
        upload_id: Optional[str] = None,
    ) -> str:
        """
        Format transcript as a separate file.

        Args:
            transcription_text: The transcription content
            title: Note title for the transcript
            upload_id: Optional upload identifier

        Returns:
            str: Formatted transcript markdown
        """
        if not transcription_text.strip():
            logger.warning("Empty transcription text provided to transcript formatter")
            transcription_text = "No transcription content available."

        # Use provided title or create a fallback, make it lowercase
        base_title = (title or "voice note").lower()
        transcript_title = f"{base_title} - transcript"

        # Format the date
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Build the transcript content
        content_parts = [
            f"# {transcript_title}",
            f"date: {current_date}",
            "",
            transcription_text.strip(),
        ]

        result = "\n".join(content_parts)

        logger.info(
            "Formatted transcript for Obsidian",
            extra={
                "upload_id": upload_id,
                "title": transcript_title,
                "content_length": len(result),
            },
        )

        return result

    def _clean_keywords_for_obsidian(self, keywords: List[str]) -> List[str]:
        """
        Clean and validate keywords for Obsidian tag compatibility.

        Args:
            keywords: Raw keywords from extraction

        Returns:
            list[str]: Cleaned keywords suitable for Obsidian tags
        """
        if not keywords:
            return []

        clean_keywords = []

        for keyword in keywords:
            if not keyword or not isinstance(keyword, str):
                continue

            # Clean the keyword
            cleaned = keyword.strip()

            # Remove common punctuation and normalize, but keep commas temporarily
            cleaned = (
                cleaned.replace(".", "")
                .replace("!", "")
                .replace("?", "")
                .replace(";", "")
                .replace(":", "")
            )

            # Replace commas with hyphens before removing spaces
            cleaned = cleaned.replace(",", "-")

            # Replace spaces with hyphens for Obsidian tag compatibility
            cleaned = cleaned.replace(" ", "-").replace("_", "-")

            # Remove multiple consecutive hyphens
            while "--" in cleaned:
                cleaned = cleaned.replace("--", "-")

            # Remove leading/trailing hyphens
            cleaned = cleaned.strip("-")

            # Only include non-empty, reasonable-length keywords
            if cleaned and 2 <= len(cleaned) <= 30:
                # Convert to lowercase for consistency
                cleaned = cleaned.lower()
                if cleaned not in clean_keywords:  # Avoid duplicates
                    clean_keywords.append(cleaned)

        logger.debug(
            "Cleaned keywords for Obsidian",
            extra={
                "original_count": len(keywords),
                "cleaned_count": len(clean_keywords),
                "original": keywords[:3],  # Log first 3 for debugging
                "cleaned": clean_keywords[:3],
            },
        )

        return clean_keywords

    def format_for_obsidian_filename(
        self, title: str, is_transcript: bool = False
    ) -> str:
        """
        Generate a safe filename for Obsidian based on title (lowercase with spaces).

        Args:
            title: The note title to use for filename
            is_transcript: Whether this is a transcript file

        Returns:
            str: Safe filename without extension (lowercase with spaces)
        """
        # Start with the title, make lowercase
        filename = title.strip().lower()

        # Add transcript suffix if needed
        if is_transcript:
            filename += " transcript"

        # Replace problematic characters but keep spaces
        filename = filename.replace("'", "")
        filename = filename.replace('"', "")
        filename = filename.replace(":", "")
        filename = filename.replace(";", "")
        filename = filename.replace(",", "")
        filename = filename.replace("?", "")
        filename = filename.replace("!", "")
        filename = filename.replace("/", " ")
        filename = filename.replace("\\", " ")
        filename = filename.replace("|", " ")
        filename = filename.replace("\t", " ")
        filename = filename.replace("\n", " ")
        filename = filename.replace("\r", " ")

        # Replace multiple consecutive spaces with single space
        while "  " in filename:
            filename = filename.replace("  ", " ")

        # Remove leading/trailing spaces
        filename = filename.strip()

        # Keep only safe characters (letters, numbers, spaces, hyphens, underscores)
        safe_chars = "abcdefghijklmnopqrstuvwxyz0123456789 -_"
        filename = "".join(c for c in filename if c in safe_chars)

        # Ensure filename is not empty and not too long
        if not filename:
            filename = "voice note"
        elif len(filename) > 100:
            filename = filename[:100].rstrip()

        return filename


# Global service instance
markdown_formatter = MarkdownFormatter()
