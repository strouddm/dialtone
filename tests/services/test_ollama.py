"""Tests for Ollama service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.services.ollama import OllamaService
from app.core.exceptions import ServiceUnavailableError


class TestOllamaService:
    """Test cases for OllamaService."""

    @pytest.fixture
    def ollama_service(self):
        """Create OllamaService instance for testing."""
        return OllamaService()

    @pytest.fixture
    def mock_client(self):
        """Mock HTTP client."""
        client = AsyncMock(spec=httpx.AsyncClient)
        return client

    def test_init(self, ollama_service):
        """Test OllamaService initialization."""
        assert ollama_service.base_url == "http://ollama:11434"
        assert ollama_service.model == "llama2:7b"
        assert ollama_service.timeout == 30
        assert ollama_service.max_retries == 3
        assert ollama_service.enabled is True
        assert ollama_service._client is None

    @pytest.mark.asyncio
    async def test_get_client_creates_new_client(self, ollama_service):
        """Test that _get_client creates a new client when needed."""
        client = await ollama_service._get_client()
        assert client is not None
        assert ollama_service._client is client
        
        # Verify same client is returned on subsequent calls
        same_client = await ollama_service._get_client()
        assert same_client is client
        
        await ollama_service.close()

    @pytest.mark.asyncio
    async def test_close_client(self, ollama_service):
        """Test closing HTTP client."""
        client = await ollama_service._get_client()
        assert ollama_service._client is not None
        
        await ollama_service.close()
        assert ollama_service._client is None

    @pytest.mark.asyncio
    async def test_health_check_success(self, ollama_service, mock_client):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get.return_value = mock_response
        
        with patch.object(ollama_service, '_get_client', return_value=mock_client):
            result = await ollama_service.health_check()
            
        assert result is True
        mock_client.get.assert_called_once_with("/api/tags")

    @pytest.mark.asyncio
    async def test_health_check_failure(self, ollama_service, mock_client):
        """Test health check failure."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client.get.return_value = mock_response
        
        with patch.object(ollama_service, '_get_client', return_value=mock_client):
            result = await ollama_service.health_check()
            
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_disabled_service(self):
        """Test health check when service is disabled."""
        service = OllamaService()
        service.enabled = False
        
        result = await service.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self, ollama_service, mock_client):
        """Test health check with connection error."""
        mock_client.get.side_effect = httpx.ConnectError("Connection failed")
        
        with patch.object(ollama_service, '_get_client', return_value=mock_client):
            result = await ollama_service.health_check()
            
        assert result is False

    @pytest.mark.asyncio
    async def test_ensure_model_loaded_already_loaded(self, ollama_service, mock_client):
        """Test ensure_model_loaded when model is already available."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "llama2:7b"}, {"name": "other:model"}]
        }
        mock_client.get.return_value = mock_response
        
        with patch.object(ollama_service, '_get_client', return_value=mock_client):
            result = await ollama_service.ensure_model_loaded()
            
        assert result is True
        mock_client.get.assert_called_once_with("/api/tags")

    @pytest.mark.asyncio
    async def test_ensure_model_loaded_needs_pulling(self, ollama_service, mock_client):
        """Test ensure_model_loaded when model needs to be pulled."""
        # First call returns no models, second call returns success
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"models": []}
        
        mock_pull_response = MagicMock()
        mock_pull_response.status_code = 200
        
        mock_client.get.return_value = mock_get_response
        mock_client.post.return_value = mock_pull_response
        
        with patch.object(ollama_service, '_get_client', return_value=mock_client):
            result = await ollama_service.ensure_model_loaded()
            
        assert result is True
        mock_client.post.assert_called_once_with(
            "/api/pull",
            json={"name": "llama2:7b"},
            timeout=300,
        )

    @pytest.mark.asyncio
    async def test_ensure_model_loaded_disabled(self):
        """Test ensure_model_loaded when service is disabled."""
        service = OllamaService()
        service.enabled = False
        
        result = await service.ensure_model_loaded()
        assert result is False

    @pytest.mark.asyncio
    async def test_generate_summary_success(self, ollama_service, mock_client):
        """Test successful bullet-point summary generation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "• Main point about the meeting\n• Key decision that was made\n• Action items for follow-up"
        }
        mock_client.post.return_value = mock_response
        
        with patch.object(ollama_service, '_get_client', return_value=mock_client):
            result = await ollama_service.generate_summary("Test text content about a meeting with decisions")
            
        # Check that bullet points are properly formatted
        assert "- Main point about the meeting" in result
        assert "- Key decision that was made" in result
        assert "- Action items for follow-up" in result
        
        # Verify API call was made correctly with bullet-point prompt
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/api/generate"
        assert call_args[1]["json"]["model"] == "llama2:7b"
        prompt = call_args[1]["json"]["prompt"]
        assert "bullet-point summary" in prompt
        assert "3-5 bullet points maximum" in prompt
        assert "Test text content" in prompt

    @pytest.mark.asyncio
    async def test_generate_summary_empty_text(self, ollama_service):
        """Test summary generation with empty text."""
        result = await ollama_service.generate_summary("")
        assert result == "No content to summarize."
        
        result = await ollama_service.generate_summary("   ")
        assert result == "No content to summarize."

    @pytest.mark.asyncio
    async def test_generate_summary_disabled_service(self):
        """Test summary generation when service is disabled."""
        service = OllamaService()
        service.enabled = False
        
        with pytest.raises(ServiceUnavailableError):
            await service.generate_summary("Test text")

    @pytest.mark.asyncio
    async def test_generate_summary_empty_response(self, ollama_service, mock_client):
        """Test summary generation with empty response uses fallback."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": ""}
        mock_client.post.return_value = mock_response
        
        with patch.object(ollama_service, '_get_client', return_value=mock_client):
            result = await ollama_service.generate_summary("This is a test sentence about a meeting. We discussed important topics. Action items were assigned.")
            
        # Should get fallback summary with bullet points
        assert result.startswith("- ")
        assert "test sentence" in result or "meeting" in result

    @pytest.mark.asyncio
    async def test_generate_summary_api_error_uses_fallback(self, ollama_service, mock_client):
        """Test summary generation with API error uses fallback instead of raising."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_client.post.return_value = mock_response
        
        with patch.object(ollama_service, '_get_client', return_value=mock_client):
            result = await ollama_service.generate_summary("This is a test about a project meeting. Important decisions were made. We have action items.")
                
        # Should get fallback summary instead of error
        assert result.startswith("- ")
        assert "test" in result or "project" in result or "meeting" in result

    @pytest.mark.asyncio
    async def test_generate_summary_with_retries(self, ollama_service, mock_client):
        """Test summary generation with retry logic."""
        # First call fails, second succeeds
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"response": "- Successful summary after retry\n- Key points identified"}
        
        mock_client.post.side_effect = [
            httpx.TimeoutException("Request timeout"),
            success_response
        ]
        
        with patch.object(ollama_service, '_get_client', return_value=mock_client):
            with patch('asyncio.sleep'):  # Speed up test by mocking sleep
                result = await ollama_service.generate_summary("Test text for retry scenario")
                
        assert "- Successful summary after retry" in result
        assert "- Key points identified" in result
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_extract_keywords_success(self, ollama_service, mock_client):
        """Test successful keyword extraction."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "keyword1\nkeyword2\n• keyword3\n- keyword4\nkeyword5"
        }
        mock_client.post.return_value = mock_response
        
        with patch.object(ollama_service, '_get_client', return_value=mock_client):
            result = await ollama_service.extract_keywords("Test text content")
            
        assert len(result) == 5
        assert "keyword1" in result
        assert "keyword2" in result
        assert "keyword3" in result
        assert "keyword4" in result
        assert "keyword5" in result

    @pytest.mark.asyncio
    async def test_extract_keywords_empty_text(self, ollama_service):
        """Test keyword extraction with empty text."""
        result = await ollama_service.extract_keywords("")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_keywords_disabled_service(self):
        """Test keyword extraction when service is disabled."""
        service = OllamaService()
        service.enabled = False
        
        with pytest.raises(ServiceUnavailableError):
            await service.extract_keywords("Test text")

    @pytest.mark.asyncio
    async def test_extract_keywords_failure_returns_empty(self, ollama_service, mock_client):
        """Test keyword extraction returns empty list on failure."""
        mock_client.post.side_effect = httpx.ConnectError("Connection failed")
        
        with patch.object(ollama_service, '_get_client', return_value=mock_client):
            result = await ollama_service.extract_keywords("Test text")
            
        assert result == []

    @pytest.mark.asyncio
    async def test_generate_summary_max_words_parameter(self, ollama_service, mock_client):
        """Test summary generation with different max_words parameter."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "- Short summary point\n- Another brief point"
        }
        mock_client.post.return_value = mock_response
        
        with patch.object(ollama_service, '_get_client', return_value=mock_client):
            result = await ollama_service.generate_summary("Test text", max_words=100)
            
        # Verify the max_words was used in the prompt
        call_args = mock_client.post.call_args
        prompt = call_args[1]["json"]["prompt"]
        assert "under 100 words" in prompt
        
    def test_validate_summary_quality_good_summary(self, ollama_service):
        """Test quality validation accepts good bullet-point summaries."""
        good_summary = "- Main point about the meeting\n- Key decision made\n- Action items assigned"
        result = ollama_service._validate_summary_quality(good_summary, "original text")
        assert result is True
        
    def test_validate_summary_quality_poor_summary(self, ollama_service):
        """Test quality validation rejects poor summaries."""
        # Too short
        assert ollama_service._validate_summary_quality("Short", "original") is False
        
        # Generic response
        generic = "This is a summary of the text provided above."
        assert ollama_service._validate_summary_quality(generic, "original") is False
        
        # No bullet points
        no_bullets = "This text talks about various topics and contains information."
        assert ollama_service._validate_summary_quality(no_bullets, "original") is False
        
    def test_format_bullet_points(self, ollama_service):
        """Test bullet point formatting normalization."""
        # Various bullet formats
        mixed_bullets = "• First point\n* Second point\n1. Third point\n- Fourth point"
        result = ollama_service._format_bullet_points(mixed_bullets)
        
        lines = result.split("\n")
        assert all(line.startswith("- ") for line in lines)
        assert len(lines) == 4
        
    def test_create_fallback_summary(self, ollama_service):
        """Test fallback summary creation."""
        text = "This is the first sentence. This is another sentence with content. Here is a third sentence."
        result = ollama_service._create_fallback_summary(text, 150)
        
        assert result.startswith("- ")
        assert "first sentence" in result
        lines = result.split("\n")
        assert all(line.startswith("- ") for line in lines if line.strip())

    def test_get_status(self, ollama_service):
        """Test getting service status."""
        status = ollama_service.get_status()
        
        assert status["enabled"] is True
        assert status["base_url"] == "http://ollama:11434"
        assert status["model"] == "llama2:7b"
        assert status["timeout"] == 30
        assert status["max_retries"] == 3