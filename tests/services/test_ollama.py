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
        """Test successful summary generation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "• Main point 1\n• Key insight 2\n• Important detail 3"
        }
        mock_client.post.return_value = mock_response
        
        with patch.object(ollama_service, '_get_client', return_value=mock_client):
            result = await ollama_service.generate_summary("Test text content")
            
        assert "Main point 1" in result
        assert "Key insight 2" in result
        assert "Important detail 3" in result
        
        # Verify API call was made correctly
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/api/generate"
        assert call_args[1]["json"]["model"] == "llama2:7b"
        assert "Test text content" in call_args[1]["json"]["prompt"]

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
        """Test summary generation with empty response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": ""}
        mock_client.post.return_value = mock_response
        
        with patch.object(ollama_service, '_get_client', return_value=mock_client):
            result = await ollama_service.generate_summary("Test text")
            
        assert result == "Unable to generate summary - empty response."

    @pytest.mark.asyncio
    async def test_generate_summary_api_error(self, ollama_service, mock_client):
        """Test summary generation with API error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_client.post.return_value = mock_response
        
        with patch.object(ollama_service, '_get_client', return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await ollama_service.generate_summary("Test text")
                
        assert "Ollama service unavailable" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_summary_with_retries(self, ollama_service, mock_client):
        """Test summary generation with retry logic."""
        # First call fails, second succeeds
        mock_client.post.side_effect = [
            httpx.TimeoutException("Request timeout"),
            MagicMock(status_code=200, json=lambda: {"response": "Success after retry"})
        ]
        
        with patch.object(ollama_service, '_get_client', return_value=mock_client):
            with patch('asyncio.sleep'):  # Speed up test by mocking sleep
                result = await ollama_service.generate_summary("Test text")
                
        assert result == "Success after retry"
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

    def test_get_status(self, ollama_service):
        """Test getting service status."""
        status = ollama_service.get_status()
        
        assert status["enabled"] is True
        assert status["base_url"] == "http://ollama:11434"
        assert status["model"] == "llama2:7b"
        assert status["timeout"] == 30
        assert status["max_retries"] == 3