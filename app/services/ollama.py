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

        # Create bullet-point specific summarization prompt
        prompt = f"""Create a concise bullet-point summary of the following transcription.
Focus on key points, decisions, and action items:

- Use 3-5 bullet points maximum
- Keep each point under 25 words
- Prioritize actionable insights
- Maintain original context and intent
- Total summary should be under {max_words} words

Transcription: {text.strip()}

Summary:"""

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
                            "Successfully generated bullet-point summary using Ollama"
                        )
                        return self._format_bullet_points(summary)
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

        # Check for bullet points or structured format
        has_bullets = bool(
            "•" in summary
            or "*" in summary
            or "-" in summary
            or any(
                line.strip().startswith(("•", "*", "-", "1.", "2.", "3."))
                for line in summary.split("\n")
            )
        )

        if not has_bullets:
            logger.debug("Summary lacks bullet point structure")
            return False

        # Check word count is reasonable
        word_count = len(summary.split())
        if word_count < 10 or word_count > 400:
            logger.debug(f"Summary word count ({word_count}) outside acceptable range")
            return False

        return True

    def _format_bullet_points(self, summary: str) -> str:
        """
        Ensure consistent bullet point formatting.

        Args:
            summary: Raw summary text

        Returns:
            str: Formatted summary with consistent bullet points
        """
        lines = summary.split("\n")
        formatted_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Normalize bullet points
            if line.startswith(("•", "*", "-", "1.", "2.", "3.", "4.", "5.")):
                # Replace various bullet formats with consistent dash
                if line.startswith(("•", "*")):
                    line = "- " + line[1:].strip()
                elif line[0].isdigit() and line[1:3] in [". ", ".\t"]:
                    line = "- " + line[2:].strip()
                elif not line.startswith("- "):
                    line = "- " + line.lstrip("- ").strip()

                formatted_lines.append(line)
            elif formatted_lines:  # Continuation of previous bullet
                formatted_lines[-1] += " " + line
            else:  # First line without bullet
                formatted_lines.append("- " + line)

        return "\n".join(formatted_lines[:5])  # Limit to 5 bullet points

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
