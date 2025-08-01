"""Ollama client service for AI summarization."""

import asyncio
import logging
from typing import Dict, Any, Optional

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
                logger.error(f"Failed to load model {self.model}: {pull_response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error loading model {self.model}: {e}")
            return False

    async def generate_summary(self, text: str, max_length: int = 200) -> str:
        """
        Generate AI summary of the provided text using Ollama.
        
        Args:
            text: Text to summarize
            max_length: Maximum length of summary in words
            
        Returns:
            str: Generated summary
            
        Raises:
            ServiceUnavailableError: If Ollama service is unavailable
        """
        if not self.enabled:
            raise ServiceUnavailableError("Ollama service is disabled")

        if not text.strip():
            return "No content to summarize."

        # Create summarization prompt
        prompt = f"""Please create a concise summary of the following text in bullet points. 
Keep it under {max_length} words and focus on the main ideas and key points:

Text: {text.strip()}

Summary:"""

        retry_count = 0
        last_error = None

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
                            "max_tokens": max_length * 2,  # Allow some buffer
                        }
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    summary = result.get("response", "").strip()
                    
                    if summary:
                        logger.info("Successfully generated summary using Ollama")
                        return summary
                    else:
                        logger.warning("Ollama returned empty summary")
                        return "Unable to generate summary - empty response."
                else:
                    logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                    last_error = f"API error: {response.status_code}"

            except httpx.TimeoutException:
                last_error = "Request timeout"
                logger.warning(f"Ollama request timeout (attempt {retry_count + 1})")
            except httpx.ConnectError:
                last_error = "Connection error"
                logger.warning(f"Cannot connect to Ollama service (attempt {retry_count + 1})")
            except Exception as e:
                last_error = str(e)
                logger.error(f"Unexpected error calling Ollama (attempt {retry_count + 1}): {e}")

            retry_count += 1
            if retry_count < self.max_retries:
                await asyncio.sleep(2 ** retry_count)  # Exponential backoff

        # All retries failed
        error_msg = f"Ollama service unavailable after {self.max_retries} attempts. Last error: {last_error}"
        logger.error(error_msg)
        raise ServiceUnavailableError(error_msg)

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
                    }
                }
            )

            if response.status_code == 200:
                result = response.json()
                keywords_text = result.get("response", "").strip()
                
                if keywords_text:
                    # Parse keywords from response
                    keywords = []
                    for line in keywords_text.split('\n'):
                        keyword = line.strip().strip('-').strip('•').strip('*').strip()
                        if keyword and len(keywords) < max_keywords:
                            keywords.append(keyword)
                    
                    logger.info(f"Extracted {len(keywords)} keywords using Ollama")
                    return keywords[:max_keywords]
                    
        except Exception as e:
            logger.warning(f"Failed to extract keywords with Ollama: {e}")

        # Return empty list on failure (non-critical feature)
        return []

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