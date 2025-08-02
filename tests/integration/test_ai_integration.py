"""AI services integration tests for Whisper and Ollama."""

import pytest
from typing import Dict, Any
from unittest.mock import AsyncMock, patch

from fastapi import status
from httpx import AsyncClient


@pytest.mark.integration
class TestAIServicesIntegration:
    """Test integration with AI services (Whisper and Ollama)."""

    async def test_whisper_transcription_accuracy(
        self,
        async_client: AsyncClient,
        test_audio_content: bytes,
        setup_test_environment: Dict[str, Any]
    ):
        """Test Whisper transcription accuracy and quality metrics."""
        # Upload test audio
        files = {"file": ("accuracy_test.webm", test_audio_content, "audio/webm")}
        upload_response = await async_client.post(
            "/api/v1/audio/upload",
            files=files,
            data={"description": "Transcription accuracy test"}
        )
        
        upload_data = upload_response.json()
        upload_id = upload_data["upload_id"]
        
        # Test with real Whisper model simulation
        with patch("app.services.whisper_model.WhisperModel") as mock_whisper:
            mock_instance = AsyncMock()
            
            # Simulate high-quality transcription with detailed metrics
            mock_instance.transcribe.return_value = {
                "text": "This is a comprehensive test of the Whisper transcription service. The system should accurately transcribe spoken words with proper punctuation and capitalization.",
                "segments": [
                    {
                        "id": 0,
                        "seek": 0,
                        "start": 0.0,
                        "end": 5.2,
                        "text": "This is a comprehensive test of the Whisper transcription service.",
                        "avg_logprob": -0.2,
                        "compression_ratio": 1.4,
                        "no_speech_prob": 0.01
                    },
                    {
                        "id": 1,
                        "seek": 520,
                        "start": 5.2,
                        "end": 10.8,
                        "text": "The system should accurately transcribe spoken words with proper punctuation and capitalization.",
                        "avg_logprob": -0.18,
                        "compression_ratio": 1.3,
                        "no_speech_prob": 0.02
                    }
                ],
                "language": "en",
                "language_probability": 0.98
            }
            mock_whisper.return_value = mock_instance
            
            transcription_response = await async_client.post(
                f"/api/v1/audio/{upload_id}/transcribe"
            )
            
            assert transcription_response.status_code == status.HTTP_200_OK
            transcription_data = transcription_response.json()
            
            # Verify transcription quality
            assert "transcription" in transcription_data
            transcription = transcription_data["transcription"]
            
            # Check accuracy indicators
            assert "comprehensive test" in transcription["text"]
            assert "Whisper transcription service" in transcription["text"]
            assert transcription["text"].endswith(".")  # Proper punctuation
            
            # Verify segment details if available
            if "segments" in transcription:
                segments = transcription["segments"]
                assert len(segments) == 2
                assert all(seg["avg_logprob"] > -0.5 for seg in segments)  # High confidence
                assert all(seg["no_speech_prob"] < 0.1 for seg in segments)  # Clear speech
            
            # Verify language detection
            if "language" in transcription:
                assert transcription["language"] == "en"
                assert transcription["language_probability"] > 0.9

    async def test_ollama_summarization_quality(
        self,
        async_client: AsyncClient,
        test_audio_content: bytes,
        test_transcription_data: Dict[str, Any],
        setup_test_environment: Dict[str, Any]
    ):
        """Test Ollama summarization quality and keyword extraction."""
        # Upload and transcribe first
        files = {"file": ("summary_test.webm", test_audio_content, "audio/webm")}
        upload_response = await async_client.post(
            "/api/v1/audio/upload",
            files=files,
            data={"description": "Summarization quality test"}
        )
        
        upload_data = upload_response.json()
        upload_id = upload_data["upload_id"]
        
        # Mock transcription result
        with patch("app.services.whisper_model.WhisperModel") as mock_whisper:
            mock_whisper_instance = AsyncMock()
            mock_whisper_instance.transcribe.return_value = test_transcription_data
            mock_whisper.return_value = mock_whisper_instance
            
            await async_client.post(f"/api/v1/audio/{upload_id}/transcribe")
        
        # Test Ollama summarization
        with patch("app.services.ollama.OllamaService") as mock_ollama:
            mock_ollama_instance = AsyncMock()
            
            # Simulate high-quality summarization
            mock_ollama_instance.summarize.return_value = {
                "summary": "- Comprehensive transcription analysis demonstrates system capabilities\n- Multiple sentence structures processed effectively\n- Speech recognition accuracy meets quality standards\n- Punctuation and capitalization handled correctly\n- Natural speech patterns successfully interpreted",
                "keywords": ["transcription", "analysis", "speech", "recognition", "quality", "accuracy"]
            }
            mock_ollama_instance.is_healthy.return_value = True
            mock_ollama.return_value = mock_ollama_instance
            
            summary_response = await async_client.post(
                f"/api/v1/audio/{upload_id}/summarize"
            )
            
            assert summary_response.status_code == status.HTTP_200_OK
            summary_data = summary_response.json()
            
            # Verify summary quality
            assert "summary" in summary_data
            assert "keywords" in summary_data
            
            summary_text = summary_data["summary"]
            keywords = summary_data["keywords"]
            
            # Check summary structure (bullet points as per PRD)
            assert summary_text.startswith("- ")
            assert summary_text.count("\n- ") >= 2  # Multiple bullet points
            
            # Verify keyword extraction (3-5 keywords as per PRD)
            assert 3 <= len(keywords) <= 5
            assert all(isinstance(keyword, str) for keyword in keywords)
            assert "transcription" in keywords  # Relevant keyword
            
            # Check content relevance
            assert "speech" in summary_text.lower() or "transcription" in summary_text.lower()
            assert any(keyword in ["transcription", "speech", "analysis"] for keyword in keywords)

    async def test_keyword_extraction_relevance(
        self,
        async_client: AsyncClient,
        test_audio_content: bytes,
        setup_test_environment: Dict[str, Any]
    ):
        """Test keyword extraction relevance and accuracy."""
        files = {"file": ("keyword_test.webm", test_audio_content, "audio/webm")}
        upload_response = await async_client.post(
            "/api/v1/audio/upload",
            files=files,
            data={"description": "Keyword extraction test"}
        )
        
        upload_data = upload_response.json()
        upload_id = upload_data["upload_id"]
        
        # Provide specific transcription for keyword testing
        test_transcription = {
            "text": "Today I want to discuss machine learning algorithms and their application in natural language processing. We'll cover neural networks, deep learning frameworks like TensorFlow and PyTorch, and explore transformer architectures used in modern AI systems.",
            "segments": [
                {"start": 0.0, "end": 8.0, "text": "Today I want to discuss machine learning algorithms and their application in natural language processing."},
                {"start": 8.0, "end": 16.0, "text": "We'll cover neural networks, deep learning frameworks like TensorFlow and PyTorch, and explore transformer architectures used in modern AI systems."}
            ]
        }
        
        with patch("app.services.whisper_model.WhisperModel") as mock_whisper:
            mock_whisper.return_value.transcribe.return_value = test_transcription
            await async_client.post(f"/api/v1/audio/{upload_id}/transcribe")
        
        # Test keyword extraction with technical content
        with patch("app.services.ollama.OllamaService") as mock_ollama:
            mock_ollama_instance = AsyncMock()
            mock_ollama_instance.summarize.return_value = {
                "summary": "- Discussion of machine learning algorithms and applications\n- Coverage of neural networks and deep learning frameworks\n- Exploration of transformer architectures in AI systems\n- Focus on natural language processing techniques",
                "keywords": ["machine learning", "neural networks", "deep learning", "transformers", "AI"]
            }
            mock_ollama_instance.is_healthy.return_value = True
            mock_ollama.return_value = mock_ollama_instance
            
            summary_response = await async_client.post(f"/api/v1/audio/{upload_id}/summarize")
            summary_data = summary_response.json()
            
            keywords = summary_data["keywords"]
            
            # Verify keyword relevance to content
            relevant_terms = ["machine learning", "neural networks", "deep learning", "AI", "transformers"]
            assert any(term in keywords for term in relevant_terms)
            
            # Check keyword format and quality
            assert len(keywords) >= 3
            assert all(len(keyword) > 2 for keyword in keywords)  # No trivial keywords
            assert not any(keyword.lower() in ["the", "and", "or", "but"] for keyword in keywords)  # No stop words

    async def test_ai_services_error_handling(
        self,
        async_client: AsyncClient,
        test_audio_content: bytes,
        setup_test_environment: Dict[str, Any]
    ):
        """Test AI services error handling and recovery."""
        files = {"file": ("error_test.webm", test_audio_content, "audio/webm")}
        upload_response = await async_client.post(
            "/api/v1/audio/upload",
            files=files,
            data={"description": "AI error handling test"}
        )
        
        upload_data = upload_response.json()
        upload_id = upload_data["upload_id"]
        
        # Test Whisper service failure
        with patch("app.services.whisper_model.WhisperModel") as mock_whisper:
            mock_whisper.return_value.transcribe.side_effect = Exception("Whisper model not loaded")
            
            transcription_response = await async_client.post(f"/api/v1/audio/{upload_id}/transcribe")
            
            assert transcription_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            error_data = transcription_response.json()
            assert "error" in error_data or "detail" in error_data
        
        # Test successful transcription, then Ollama failure
        with patch("app.services.whisper_model.WhisperModel") as mock_whisper:
            mock_whisper.return_value.transcribe.return_value = {
                "text": "Test transcription for error handling",
                "segments": [{"start": 0.0, "end": 3.0, "text": "Test transcription for error handling"}]
            }
            
            transcription_response = await async_client.post(f"/api/v1/audio/{upload_id}/transcribe")
            assert transcription_response.status_code == status.HTTP_200_OK
        
        # Test Ollama service failure
        with patch("app.services.ollama.OllamaService") as mock_ollama:
            mock_ollama.return_value.summarize.side_effect = Exception("Ollama service unavailable")
            mock_ollama.return_value.is_healthy.return_value = False
            
            summary_response = await async_client.post(f"/api/v1/audio/{upload_id}/summarize")
            
            # Should handle gracefully (may return error or fallback summary)
            assert summary_response.status_code in [
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                status.HTTP_503_SERVICE_UNAVAILABLE,
                status.HTTP_200_OK  # If fallback is implemented
            ]

    async def test_ai_processing_timeouts(
        self,
        async_client: AsyncClient,
        test_audio_content: bytes,
        setup_test_environment: Dict[str, Any]
    ):
        """Test AI processing timeout handling."""
        files = {"file": ("timeout_test.webm", test_audio_content, "audio/webm")}
        upload_response = await async_client.post(
            "/api/v1/audio/upload",
            files=files,
            data={"description": "Timeout handling test"}
        )
        
        upload_data = upload_response.json()
        upload_id = upload_data["upload_id"]
        
        # Test Whisper timeout simulation
        import asyncio
        
        with patch("app.services.whisper_model.WhisperModel") as mock_whisper:
            async def slow_transcribe(*args, **kwargs):
                await asyncio.sleep(60)  # Simulate very slow processing
                return {"text": "This should timeout", "segments": []}
            
            mock_whisper.return_value.transcribe = slow_transcribe
            
            # This should timeout based on processing timeout settings
            transcription_response = await async_client.post(f"/api/v1/audio/{upload_id}/transcribe")
            
            # Should handle timeout gracefully
            assert transcription_response.status_code in [
                status.HTTP_408_REQUEST_TIMEOUT,
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ]

    async def test_ai_service_health_integration(
        self,
        async_client: AsyncClient,
        setup_test_environment: Dict[str, Any]
    ):
        """Test AI service health check integration."""
        # Test health endpoint includes AI services
        health_response = await async_client.get("/api/v1/health")
        
        assert health_response.status_code == status.HTTP_200_OK
        health_data = health_response.json()
        
        # Verify AI services are included in health checks
        assert "checks" in health_data
        checks = health_data["checks"]
        
        # Should include Whisper model status
        whisper_check = next((check for check in checks if "whisper" in check["name"].lower()), None)
        assert whisper_check is not None
        
        # Should include Ollama service status if enabled
        if any(check for check in checks if "ollama" in check["name"].lower()):
            ollama_check = next((check for check in checks if "ollama" in check["name"].lower()), None)
            assert ollama_check is not None

    async def test_ai_model_loading_performance(
        self,
        async_client: AsyncClient,
        test_audio_content: bytes,
        setup_test_environment: Dict[str, Any]
    ):
        """Test AI model loading and first-request performance."""
        import time
        
        files = {"file": ("performance_test.webm", test_audio_content, "audio/webm")}
        upload_response = await async_client.post(
            "/api/v1/audio/upload",
            files=files,
            data={"description": "AI performance test"}
        )
        
        upload_data = upload_response.json()
        upload_id = upload_data["upload_id"]
        
        # Simulate cold start scenario
        with patch("app.services.whisper_model.WhisperModel") as mock_whisper:
            mock_instance = AsyncMock()
            
            async def load_and_transcribe(*args, **kwargs):
                # Simulate model loading time
                await asyncio.sleep(0.1)  # Quick simulation
                return {
                    "text": "Performance test transcription",
                    "segments": [{"start": 0.0, "end": 3.0, "text": "Performance test transcription"}]
                }
            
            mock_instance.transcribe = load_and_transcribe
            mock_whisper.return_value = mock_instance
            
            start_time = time.time()
            transcription_response = await async_client.post(f"/api/v1/audio/{upload_id}/transcribe")
            end_time = time.time()
            
            assert transcription_response.status_code == status.HTTP_200_OK
            
            # Performance assertion for API response time
            processing_time = end_time - start_time
            assert processing_time < 10.0  # Should complete within reasonable time
            
            # Verify response time meets API requirements (<500ms for API overhead)
            # Note: This excludes AI processing time in mocked scenario
            api_time = transcription_response.elapsed.total_seconds()
            assert api_time < 0.5  # API response time requirement