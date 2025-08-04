"""Ollama client service for AI summarization."""

import asyncio
import logging
from typing import Any, Dict, Optional

import httpx

from app.core.exceptions import ServiceUnavailableError
from app.core.settings import settings

logger = logging.getLogger(__name__)


class OllamaService:
    """Service for interacting with Ollama AI models."""

    def __init__(self):
        """Initialize Ollama service with configuration."""
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout
        self.max_retries = settings.ollama_max_retries
        self.enabled = settings.ollama_enabled
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
            )
        return self._client

    async def close(self):
        """Close HTTP client connections."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> bool:
        """
        Check if Ollama service is healthy and responsive.

        Returns:
            bool: True if service is healthy, False otherwise
        """
        if not self.enabled:
            logger.info("Ollama service is disabled")
            return False

        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

    async def ensure_model_loaded(self) -> bool:
        """
        Ensure the configured model is loaded and ready.

        Returns:
            bool: True if model is loaded, False otherwise
        """
        if not self.enabled:
            return False

        try:
            client = await self._get_client()

            # Check if model is already loaded
            response = await client.get("/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [model.get("name", "") for model in models]

                if self.model in model_names:
                    logger.info(f"Model {self.model} is already loaded")
                    return True

            # Try to pull/load the model
            logger.info(f"Loading model {self.model}...")
            pull_response = await client.post(
                "/api/pull",
                json={"name": self.model},
                timeout=300,  # Model loading can take time
            )

            if pull_response.status_code == 200:
                logger.info(f"Model {self.model} loaded successfully")
                return True
            else:
                logger.error(
                    f"Failed to load model {self.model}: {pull_response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"Error loading model {self.model}: {e}")
            return False

    async def generate_title(self, text: str) -> str:
        """
        Generate a 3-7 word title that captures the essence of the note.

        Args:
            text: Text to generate title from

        Returns:
            str: Generated title (3-7 words)

        Raises:
            ServiceUnavailableError: If Ollama service is unavailable
        """
        if not self.enabled:
            raise ServiceUnavailableError("Ollama service is disabled")

        if not text.strip():
            return "Untitled Note"

        # Create title generation prompt
        prompt = f"""Generate a concise 3-7 word title that captures the main essence or topic of this content. The title should be descriptive but brief, like a news headline or book chapter title.

Content: {text.strip()}

Respond with ONLY the title, no explanations or quotes:"""

        retry_count = 0

        while retry_count < self.max_retries:
            try:
                client = await self._get_client()

                response = await client.post(
                    "/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "top_p": 0.9,
                            "max_tokens": 20,
                        },
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    title = result.get("response", "").strip()

                    if title and self._validate_title_quality(title):
                        logger.info("Successfully generated title using Ollama")
                        return self._clean_title(title)
                    else:
                        logger.warning(
                            "Ollama returned low-quality title, using fallback"
                        )
                        return self._create_fallback_title(text)
                else:
                    logger.error(
                        f"Ollama API error: {response.status_code} - {response.text}"
                    )

            except httpx.TimeoutException:
                logger.warning(f"Ollama request timeout (attempt {retry_count + 1})")
            except httpx.ConnectError:
                logger.warning(
                    f"Cannot connect to Ollama service (attempt {retry_count + 1})"
                )
            except Exception as e:
                logger.error(
                    f"Unexpected error calling Ollama (attempt {retry_count + 1}): {e}"
                )

            retry_count += 1
            if retry_count < self.max_retries:
                await asyncio.sleep(2**retry_count)

        # All retries failed - return fallback title
        logger.warning(
            f"Ollama service unavailable after {self.max_retries} attempts. Using fallback title."
        )
        return self._create_fallback_title(text)

    async def generate_tags(self, text: str, max_tags: int = 3) -> list[str]:
        """
        Generate tags from the provided text (max 3).

        Args:
            text: Text to generate tags from
            max_tags: Maximum number of tags (default 3)

        Returns:
            list[str]: Generated tags (1-3 tags)

        Raises:
            ServiceUnavailableError: If Ollama service is unavailable
        """
        if not self.enabled:
            raise ServiceUnavailableError("Ollama service is disabled")

        if not text.strip():
            return []

        # Ensure max_tags is within bounds
        max_tags = max(1, min(3, max_tags))

        # Create tag generation prompt
        prompt = f"""Generate {max_tags} relevant tags from this content. Tags should be single words or short phrases that capture the main topics or themes.

Content: {text.strip()}

Respond with ONLY the tags, one per line, no explanations:"""

        retry_count = 0

        while retry_count < self.max_retries:
            try:
                client = await self._get_client()

                response = await client.post(
                    "/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "top_p": 0.8,
                            "max_tokens": 30,
                        },
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    tags_text = result.get("response", "").strip()

                    if tags_text and self._validate_tags_quality(tags_text):
                        parsed_tags = self._parse_tags(tags_text, max_tags)
                        logger.info("Successfully generated tags using Ollama")
                        return parsed_tags
                    else:
                        logger.warning(
                            "Ollama returned low-quality tags, using fallback"
                        )
                        return self._create_fallback_tags(text, max_tags)
                else:
                    logger.error(
                        f"Ollama API error: {response.status_code} - {response.text}"
                    )

            except httpx.TimeoutException:
                logger.warning(f"Ollama request timeout (attempt {retry_count + 1})")
            except httpx.ConnectError:
                logger.warning(
                    f"Cannot connect to Ollama service (attempt {retry_count + 1})"
                )
            except Exception as e:
                logger.error(
                    f"Unexpected error calling Ollama (attempt {retry_count + 1}): {e}"
                )

            retry_count += 1
            if retry_count < self.max_retries:
                await asyncio.sleep(2**retry_count)

        # All retries failed - return fallback tags
        logger.warning(
            f"Ollama service unavailable after {self.max_retries} attempts. Using fallback tags."
        )
        return self._create_fallback_tags(text, max_tags)

    async def generate_summary(self, text: str, max_words: int = 150) -> str:
        """
        Generate AI bullet-point summary of the provided text using Ollama.

        Args:
            text: Text to summarize
            max_words: Maximum length of summary in words (50-300)

        Returns:
            str: Generated bullet-point summary

        Raises:
            ServiceUnavailableError: If Ollama service is unavailable
        """
        if not self.enabled:
            raise ServiceUnavailableError("Ollama service is disabled")

        if not text.strip():
            return "No content to summarize."

        # Ensure max_words is within reasonable bounds
        max_words = max(50, min(300, max_words))

        # Create clean, direct summarization prompt
        prompt = f"""Summarize the following content clearly and concisely. Focus only on the key information and main points. Do not include any conversational elements, commentary, or your own thoughts.

Content: {text.strip()}

Provide a clean summary without any dialogue or preamble:"""

        retry_count = 0

        while retry_count < self.max_retries:
            try:
                client = await self._get_client()

                response = await client.post(
                    "/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,  # Lower temperature for more focused summaries
                            "top_p": 0.9,
                            "max_tokens": max_words * 2,  # Allow some buffer
                            "stop": ["\n\n\n"],  # Stop at multiple newlines
                        },
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    summary = result.get("response", "").strip()

                    if summary and self._validate_summary_quality(summary, text):
                        logger.info(
                            "Successfully generated narrative summary using Ollama"
                        )
                        return self._format_narrative_summary(summary)
                    else:
                        logger.warning(
                            "Ollama returned low-quality summary, using fallback"
                        )
                        return self._create_fallback_summary(text, max_words)
                else:
                    logger.error(
                        f"Ollama API error: {response.status_code} - {response.text}"
                    )

            except httpx.TimeoutException:
                logger.warning(f"Ollama request timeout (attempt {retry_count + 1})")
            except httpx.ConnectError:
                logger.warning(
                    f"Cannot connect to Ollama service (attempt {retry_count + 1})"
                )
            except Exception as e:
                logger.error(
                    f"Unexpected error calling Ollama (attempt {retry_count + 1}): {e}"
                )

            retry_count += 1
            if retry_count < self.max_retries:
                await asyncio.sleep(2**retry_count)  # Exponential backoff

        # All retries failed - return fallback summary instead of raising error
        logger.warning(
            f"Ollama service unavailable after {self.max_retries} attempts. Using fallback summary."
        )
        return self._create_fallback_summary(text, max_words)

    async def extract_keywords(self, text: str, max_keywords: int = 5) -> list[str]:
        """
        Extract key words/phrases from the provided text.

        Args:
            text: Text to extract keywords from
            max_keywords: Maximum number of keywords to extract

        Returns:
            list[str]: List of extracted keywords

        Raises:
            ServiceUnavailableError: If Ollama service is unavailable
        """
        if not self.enabled:
            raise ServiceUnavailableError("Ollama service is disabled")

        if not text.strip():
            return []

        # Create keyword extraction prompt
        prompt = f"""Extract {max_keywords} key words or short phrases from the following text.
Return only the keywords, one per line, without numbers or bullets:

Text: {text.strip()}

Keywords:"""

        try:
            client = await self._get_client()

            response = await client.post(
                "/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                        "top_p": 0.8,
                        "max_tokens": 100,
                    },
                },
            )

            if response.status_code == 200:
                result = response.json()
                keywords_text = result.get("response", "").strip()

                if keywords_text:
                    # Parse keywords from response
                    keywords: list[str] = []
                    for line in keywords_text.split("\n"):
                        keyword = line.strip().strip("-").strip("•").strip("*").strip()
                        if keyword and len(keywords) < max_keywords:
                            keywords.append(keyword)

                    logger.info(f"Extracted {len(keywords)} keywords using Ollama")
                    return keywords[:max_keywords]

        except Exception as e:
            logger.warning(f"Failed to extract keywords with Ollama: {e}")

        # Return empty list on failure (non-critical feature)
        return []

    def _validate_title_quality(self, title: str) -> bool:
        """
        Validate the quality of generated title.

        Args:
            title: Generated title to validate

        Returns:
            bool: True if title meets quality standards
        """
        if not title or len(title.strip()) < 3:
            return False

        # Check word count (3-7 words)
        word_count = len(title.split())
        if word_count < 3 or word_count > 7:
            return False

        # Check for generic responses
        generic_phrases = [
            "here is",
            "title:",
            "the title",
            "untitled",
            "summary",
        ]

        title_lower = title.lower()
        if any(phrase in title_lower for phrase in generic_phrases):
            return False

        return True

    def _clean_title(self, title: str) -> str:
        """
        Clean and format the generated title.

        Args:
            title: Raw title from AI

        Returns:
            str: Cleaned title
        """
        # Remove quotes and unwanted characters
        cleaned = title.strip().strip('"').strip("'").strip()

        # Remove common prefixes
        prefixes_to_remove = ["Title: ", "title: ", "The ", "A "]
        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix) :]

        # Capitalize first letter of each word (title case)
        cleaned = " ".join(word.capitalize() for word in cleaned.split())

        return cleaned

    def _create_fallback_title(self, text: str) -> str:
        """
        Create a fallback title when AI generation fails.

        Args:
            text: Original text to create title from

        Returns:
            str: Simple extractive title
        """
        # Extract first meaningful sentence or phrase
        sentences = text.replace("?", ".").replace("!", ".").split(".")
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]

        if not sentences:
            return "Voice Note"

        # Take first sentence and extract key words
        first_sentence = sentences[0]
        words = first_sentence.split()[:6]  # Max 6 words

        # Filter out common stop words
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "is",
            "are",
            "was",
            "were",
        }
        filtered_words = [word for word in words if word.lower() not in stop_words]

        if len(filtered_words) >= 3:
            title = " ".join(filtered_words[:5])  # Max 5 content words
        else:
            title = " ".join(words[:5])  # Fallback to first 5 words

        # Clean up punctuation and capitalize
        title = title.strip(".,!?;:").strip()
        title = " ".join(word.capitalize() for word in title.split())

        return title if title else "Voice Note"

    def _validate_tags_quality(self, tags_text: str) -> bool:
        """
        Validate the quality of generated tags.

        Args:
            tags_text: Generated tags text to validate

        Returns:
            bool: True if tags meet quality standards
        """
        if not tags_text or len(tags_text.strip()) < 2:
            return False

        # Check for generic responses
        generic_phrases = [
            "here are",
            "tags:",
            "the tags",
            "unable to",
            "cannot generate",
        ]

        tags_lower = tags_text.lower()
        if any(phrase in tags_lower for phrase in generic_phrases):
            return False

        # Check if we can parse at least one valid tag
        lines = tags_text.split("\n")
        valid_tags = 0
        for line in lines[:3]:  # Check first 3 lines
            tag = line.strip().strip("-").strip("•").strip("*").strip()
            if tag and len(tag) >= 2 and len(tag) <= 20:
                valid_tags += 1

        return valid_tags >= 1

    def _parse_tags(self, tags_text: str, max_tags: int) -> list[str]:
        """
        Parse tags from AI response.

        Args:
            tags_text: Raw tags text from AI
            max_tags: Maximum number of tags

        Returns:
            list[str]: Cleaned and validated tags
        """
        tags = []
        lines = tags_text.split("\n")

        for line in lines:
            if len(tags) >= max_tags:
                break

            # Clean the tag
            tag = line.strip().strip("-").strip("•").strip("*").strip()
            tag = tag.replace('"', "").replace("'", "")

            # Skip empty or invalid tags
            if not tag or len(tag) < 2 or len(tag) > 20:
                continue

            # Remove common prefixes
            prefixes_to_remove = ["tag:", "tags:", "- ", "• ", "* "]
            for prefix in prefixes_to_remove:
                if tag.lower().startswith(prefix):
                    tag = tag[len(prefix) :].strip()

            if tag:
                tags.append(tag)

        return tags

    def _create_fallback_tags(self, text: str, max_tags: int) -> list[str]:
        """
        Create fallback tags when AI generation fails.

        Args:
            text: Original text to create tags from
            max_tags: Maximum number of tags

        Returns:
            list[str]: Simple extractive tags
        """
        # Extract common words from text
        words = text.lower().split()

        # Filter out common stop words and short words
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "should",
            "could",
            "can",
            "may",
            "might",
            "this",
            "that",
            "these",
            "those",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "me",
            "him",
            "her",
            "us",
            "them",
            "my",
            "your",
            "his",
            "her",
            "its",
            "our",
            "their",
        }

        word_freq = {}
        for word in words:
            # Clean word
            clean_word = "".join(c for c in word if c.isalnum())
            if len(clean_word) >= 3 and clean_word not in stop_words:
                word_freq[clean_word] = word_freq.get(clean_word, 0) + 1

        # Get most frequent words
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

        tags = []
        for word, freq in sorted_words[:max_tags]:
            if freq >= 2:  # Word appears at least twice
                tags.append(word)

        # If we don't have enough tags, add some defaults
        if len(tags) == 0:
            tags = ["notes"]
        elif len(tags) == 1:
            tags.append("thoughts")

        return tags[:max_tags]

    def _validate_summary_quality(self, summary: str, original_text: str) -> bool:
        """
        Validate the quality of generated summary.

        Args:
            summary: Generated summary to validate
            original_text: Original text that was summarized

        Returns:
            bool: True if summary meets quality standards
        """
        if not summary or len(summary.strip()) < 20:
            logger.debug("Summary too short")
            return False

        # Check for generic responses
        generic_phrases = [
            "this is a summary",
            "here is a summary",
            "summary:",
            "the following is",
            "unable to summarize",
        ]

        summary_lower = summary.lower()
        if any(phrase in summary_lower for phrase in generic_phrases):
            logger.debug("Summary contains generic phrases")
            return False

        # Check for coherent content (multiple sentences or structured content)
        has_structure = bool(
            len(summary.split(".")) >= 2  # Multiple sentences
            or len(summary.split("\n")) >= 2  # Multiple lines
        )

        if not has_structure:
            logger.debug("Summary lacks coherent structure")
            return False

        # Check word count is reasonable
        word_count = len(summary.split())
        if word_count < 10 or word_count > 400:
            logger.debug(f"Summary word count ({word_count}) outside acceptable range")
            return False

        return True

    def _format_narrative_summary(self, summary: str) -> str:
        """
        Format the clean summary from the direct prompt.

        Args:
            summary: Raw summary text from AI

        Returns:
            str: Cleaned and formatted summary
        """
        lines = summary.split("\n")
        formatted_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Remove any unwanted conversational prefixes
            prefixes_to_remove = [
                "here's what",
                "i understand",
                "let me",
                "it seems",
                "the summary is:",
                "summary:",
                "in summary:",
                "to summarize:",
                "here is a summary",
            ]

            line_lower = line.lower()
            should_skip = False
            for prefix in prefixes_to_remove:
                if line_lower.startswith(prefix):
                    should_skip = True
                    break

            if should_skip:
                continue

            formatted_lines.append(line)

        # Join with proper spacing, preserving paragraphs
        result = "\n\n".join(formatted_lines) if formatted_lines else summary.strip()

        # Ensure reasonable length
        if len(result) > 800:  # Roughly 150 words max
            sentences = result.split(". ")
            truncated = ". ".join(sentences[:6]) + "."
            return truncated

        # Remove any remaining conversational elements
        result = result.replace("This summary", "The content").replace(
            "This content", "The content"
        )

        return result

    def _create_fallback_summary(self, text: str, max_words: int) -> str:
        """
        Create a simple fallback summary when AI generation fails.

        Args:
            text: Original text to summarize
            max_words: Maximum words for summary

        Returns:
            str: Simple extractive summary
        """
        sentences = text.replace("?", ".").replace("!", ".").split(".")
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]

        if not sentences:
            return "- Audio transcription completed (no detailed content extracted)"

        # Take first few sentences, respecting word limit
        summary_parts = []
        word_count = 0

        for sentence in sentences[:3]:  # Max 3 sentences
            sentence_words = len(sentence.split())
            if word_count + sentence_words > max_words:
                break
            summary_parts.append(f"- {sentence.strip()}.")
            word_count += sentence_words

        if not summary_parts:
            # If even the first sentence is too long, truncate it
            first_sentence = sentences[0].split()[: max_words // 2]
            summary_parts.append(f"- {' '.join(first_sentence)}...")

        return "\n".join(summary_parts)

    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of Ollama service.

        Returns:
            dict: Service status information
        """
        return {
            "enabled": self.enabled,
            "base_url": self.base_url,
            "model": self.model,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
        }


# Global service instance
ollama_service = OllamaService()
