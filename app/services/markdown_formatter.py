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
    ) -> str:
        """
        Format transcription with YAML frontmatter for Obsidian.

        Args:
            transcription_text: The main transcription content
            summary: Optional bullet-point summary
            keywords: Optional list of extracted keywords
            metadata: Optional additional metadata to include
            upload_id: Optional upload identifier

        Returns:
            str: Formatted markdown with YAML frontmatter
        """
        if not transcription_text.strip():
            logger.warning("Empty transcription text provided to formatter")
            transcription_text = "No transcription content available."

        # Build YAML frontmatter
        frontmatter: Dict[str, Any] = {
            "type": "voice-note",
            "created": datetime.now().isoformat(),
            "processed_by": "dialtone",
        }

        if upload_id:
            frontmatter["upload_id"] = upload_id

        if keywords and len(keywords) > 0:
            # Clean and validate keywords for Obsidian tags
            clean_keywords = self._clean_keywords_for_obsidian(keywords)
            if clean_keywords:
                frontmatter["tags"] = clean_keywords

        if metadata:
            # Merge additional metadata, avoiding conflicts
            for key, value in metadata.items():
                if key not in frontmatter:
                    frontmatter[key] = value

        # Format YAML frontmatter
        yaml_lines = ["---"]
        for key, value in frontmatter.items():
            if isinstance(value, list):
                yaml_lines.append(f"{key}:")
                for item in value:
                    yaml_lines.append(f"  - {item}")
            elif isinstance(value, str) and ("\n" in value or ":" in value):
                # Quote strings that contain special characters
                yaml_lines.append(f'{key}: "{value}"')
            else:
                yaml_lines.append(f"{key}: {value}")
        yaml_lines.append("---")
        yaml_lines.append("")

        # Build content sections
        content_parts = yaml_lines.copy()

        if summary and summary.strip():
            content_parts.extend(["## Summary", "", summary.strip(), ""])

        content_parts.extend(["## Transcription", "", transcription_text.strip()])

        result = "\n".join(content_parts)

        logger.info(
            "Formatted transcription for Obsidian",
            extra={
                "upload_id": upload_id,
                "has_summary": summary is not None,
                "keyword_count": len(keywords) if keywords else 0,
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
        self, upload_id: str, timestamp: Optional[datetime] = None
    ) -> str:
        """
        Generate a safe filename for Obsidian.

        Args:
            upload_id: Upload identifier
            timestamp: Optional timestamp, defaults to now

        Returns:
            str: Safe filename without extension
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Format timestamp for filename
        timestamp_str = timestamp.strftime("%Y-%m-%d_%H-%M")

        # Create safe filename
        filename = f"voice-note_{timestamp_str}_{upload_id[:8]}"

        # Remove any potentially problematic characters
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        filename = "".join(c for c in filename if c in safe_chars)

        return filename


# Global service instance
markdown_formatter = MarkdownFormatter()
