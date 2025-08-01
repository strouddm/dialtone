"""Integration tests for transcription API with keyword extraction."""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, Mock, patch

from app.core.settings import settings
from app.main import app


class TestTranscriptionWithKeywords:
    """Test complete transcription pipeline including keywords via API."""

    @pytest.fixture
    def mock_transcription_result(self):
        """Mock Whisper transcription result."""
        return {
            "text": "This is a test transcription about project management and team collaboration in our software development process.",
            "language": "en",
            "segments": [
                {
                    "avg_logprob": -0.2,
                    "text": "This is a test transcription about project management",
                }
            ],
        }

    @pytest.fixture
    def mock_keywords(self):
        """Mock extracted keywords."""
        return [
            "project-management",
            "team-collaboration",
            "software-development",
            "process",
        ]

    @pytest.fixture
    def mock_summary(self):
        """Mock AI-generated summary."""
        return "- Project management discussion\n- Team collaboration strategies\n- Software development process review"

    @pytest.mark.asyncio
    async def test_full_pipeline_with_keywords(
        self, mock_transcription_result, mock_keywords, mock_summary
    ):
        """Test complete transcription pipeline including keywords."""
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
                        "duration": 15.5,
                        "format": "webm",
                        "sample_rate": 16000,
                        "channels": 1,
                    }
                ),
                is_conversion_needed=Mock(return_value=False),
            ),
            ollama_service=Mock(
                health_check=AsyncMock(return_value=True),
                generate_summary=AsyncMock(return_value=mock_summary),
                extract_keywords=AsyncMock(return_value=mock_keywords),
            ),
        ), patch("app.services.transcription.Path") as mock_path:
            # Mock file system
            mock_upload_dir = Mock()
            mock_upload_dir.exists.return_value = True
            mock_audio_file = Mock()
            mock_audio_file.name = "test.webm"
            mock_upload_dir.glob.return_value = [mock_audio_file]
            mock_path.return_value = mock_upload_dir

            # Enable keyword extraction
            original_enabled = settings.keyword_extraction_enabled
            settings.keyword_extraction_enabled = True

            try:
                async with AsyncClient(app=app, base_url="http://test") as client:
                    response = await client.post(
                        "/api/v1/audio/transcribe",
                        json={
                            "upload_id": "test_upload_123",
                            "language": "en",
                            "include_summary": True,
                            "max_summary_words": 150,
                        },
                    )

                assert response.status_code == 200
                data = response.json()

                # Verify transcription data
                assert data["upload_id"] == "test_upload_123"
                assert data["status"] == "completed"
                assert "processing_time_seconds" in data
                assert isinstance(data["processing_time_seconds"], float)

                # Verify transcription content
                assert "transcription" in data
                transcription = data["transcription"]
                assert transcription["text"] == mock_transcription_result["text"]
                assert transcription["language"] == "en"
                assert transcription["duration_seconds"] == 15.5
                assert "confidence" in transcription

                # Verify summary
                assert "summary" in data
                assert data["summary"] == mock_summary
                assert "summary_processing_time" in data

                # Verify keywords
                assert "keywords" in data
                assert data["keywords"] == mock_keywords
                assert "keyword_processing_time" in data
                assert isinstance(data["keyword_processing_time"], float)

            finally:
                settings.keyword_extraction_enabled = original_enabled

    @pytest.mark.asyncio
    async def test_api_response_structure_includes_keywords(
        self, mock_transcription_result, mock_keywords
    ):
        """Test API response structure includes keyword fields."""
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
        ), patch("app.services.transcription.Path") as mock_path:
            # Mock file system
            mock_upload_dir = Mock()
            mock_upload_dir.exists.return_value = True
            mock_audio_file = Mock()
            mock_audio_file.name = "test.webm"
            mock_upload_dir.glob.return_value = [mock_audio_file]
            mock_path.return_value = mock_upload_dir

            # Enable keyword extraction
            original_enabled = settings.keyword_extraction_enabled
            settings.keyword_extraction_enabled = True

            try:
                async with AsyncClient(app=app, base_url="http://test") as client:
                    response = await client.post(
                        "/api/v1/audio/transcribe",
                        json={
                            "upload_id": "test_upload_123",
                            "language": "en",
                            "include_summary": False,
                        },
                    )

                assert response.status_code == 200
                data = response.json()

                # Verify required fields are present
                required_fields = [
                    "upload_id",
                    "transcription",
                    "processing_time_seconds",
                    "status",
                    "keywords",
                    "keyword_processing_time",
                ]

                for field in required_fields:
                    assert field in data, f"Missing required field: {field}"

                # Verify data types
                assert isinstance(data["keywords"], list)
                assert all(isinstance(keyword, str) for keyword in data["keywords"])
                assert isinstance(data["keyword_processing_time"], (float, type(None)))

            finally:
                settings.keyword_extraction_enabled = original_enabled

    @pytest.mark.asyncio
    async def test_keywords_disabled_via_configuration(self, mock_transcription_result):
        """Test that keywords are not included when extraction is disabled."""
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
        ), patch("app.services.transcription.Path") as mock_path:
            # Mock file system
            mock_upload_dir = Mock()
            mock_upload_dir.exists.return_value = True
            mock_audio_file = Mock()
            mock_audio_file.name = "test.webm"
            mock_upload_dir.glob.return_value = [mock_audio_file]
            mock_path.return_value = mock_upload_dir

            # Disable keyword extraction
            original_enabled = settings.keyword_extraction_enabled
            settings.keyword_extraction_enabled = False

            try:
                async with AsyncClient(app=app, base_url="http://test") as client:
                    response = await client.post(
                        "/api/v1/audio/transcribe",
                        json={
                            "upload_id": "test_upload_123",
                            "language": "en",
                            "include_summary": False,
                        },
                    )

                assert response.status_code == 200
                data = response.json()

                # Verify keyword fields are not included when disabled
                assert "keywords" not in data
                assert "keyword_processing_time" not in data

                # Verify other fields are still present
                assert "upload_id" in data
                assert "transcription" in data
                assert "status" in data

            finally:
                settings.keyword_extraction_enabled = original_enabled

    @pytest.mark.asyncio
    async def test_keyword_extraction_with_service_failure(
        self, mock_transcription_result
    ):
        """Test API behavior when keyword extraction fails."""
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
                extract_keywords=AsyncMock(side_effect=Exception("Service failure")),
            ),
        ), patch("app.services.transcription.Path") as mock_path:
            # Mock file system
            mock_upload_dir = Mock()
            mock_upload_dir.exists.return_value = True
            mock_audio_file = Mock()
            mock_audio_file.name = "test.webm"
            mock_upload_dir.glob.return_value = [mock_audio_file]
            mock_path.return_value = mock_upload_dir

            # Enable keyword extraction
            original_enabled = settings.keyword_extraction_enabled
            settings.keyword_extraction_enabled = True

            try:
                async with AsyncClient(app=app, base_url="http://test") as client:
                    response = await client.post(
                        "/api/v1/audio/transcribe",
                        json={
                            "upload_id": "test_upload_123",
                            "language": "en",
                            "include_summary": False,
                        },
                    )

                # Should still succeed with empty keywords
                assert response.status_code == 200
                data = response.json()

                assert data["status"] == "completed"
                assert "keywords" in data
                assert data["keywords"] == []  # Empty list on failure
                assert "keyword_processing_time" in data

            finally:
                settings.keyword_extraction_enabled = original_enabled

    @pytest.mark.asyncio
    async def test_keyword_configuration_validation(self, mock_transcription_result):
        """Test that keyword count configuration is properly validated."""
        mock_many_keywords = [f"keyword{i}" for i in range(15)]  # More than max allowed

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
                extract_keywords=AsyncMock(
                    return_value=mock_many_keywords[:3]
                ),  # Respects limit
            ),
        ), patch("app.services.transcription.Path") as mock_path:
            # Mock file system
            mock_upload_dir = Mock()
            mock_upload_dir.exists.return_value = True
            mock_audio_file = Mock()
            mock_audio_file.name = "test.webm"
            mock_upload_dir.glob.return_value = [mock_audio_file]
            mock_path.return_value = mock_upload_dir

            # Set keyword count limit
            original_enabled = settings.keyword_extraction_enabled
            original_count = settings.keyword_max_count
            settings.keyword_extraction_enabled = True
            settings.keyword_max_count = 3

            try:
                async with AsyncClient(app=app, base_url="http://test") as client:
                    response = await client.post(
                        "/api/v1/audio/transcribe",
                        json={
                            "upload_id": "test_upload_123",
                            "language": "en",
                        },
                    )

                assert response.status_code == 200
                data = response.json()

                # Verify keyword count respects configuration
                assert "keywords" in data
                assert len(data["keywords"]) <= 3
                assert data["keywords"] == mock_many_keywords[:3]

            finally:
                settings.keyword_extraction_enabled = original_enabled
                settings.keyword_max_count = original_count

    @pytest.mark.asyncio
    async def test_performance_impact_of_keyword_extraction(
        self, mock_transcription_result, mock_keywords
    ):
        """Test that keyword extraction doesn't significantly impact performance."""
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
        ), patch("app.services.transcription.Path") as mock_path:
            # Mock file system
            mock_upload_dir = Mock()
            mock_upload_dir.exists.return_value = True
            mock_audio_file = Mock()
            mock_audio_file.name = "test.webm"
            mock_upload_dir.glob.return_value = [mock_audio_file]
            mock_path.return_value = mock_upload_dir

            # Enable keyword extraction
            original_enabled = settings.keyword_extraction_enabled
            settings.keyword_extraction_enabled = True

            try:
                async with AsyncClient(app=app, base_url="http://test") as client:
                    response = await client.post(
                        "/api/v1/audio/transcribe",
                        json={
                            "upload_id": "test_upload_123",
                            "language": "en",
                        },
                    )

                assert response.status_code == 200
                data = response.json()

                # Verify performance metrics are reasonable
                assert (
                    data["processing_time_seconds"] < 30
                )  # Total should be under 30s for test

                if (
                    "keyword_processing_time" in data
                    and data["keyword_processing_time"]
                ):
                    # Keyword extraction should be fast
                    assert data["keyword_processing_time"] < 5  # Should be under 5s

                    # Keyword extraction should be small portion of total time
                    keyword_ratio = (
                        data["keyword_processing_time"]
                        / data["processing_time_seconds"]
                    )
                    assert keyword_ratio < 0.5  # Less than 50% of total time

            finally:
                settings.keyword_extraction_enabled = original_enabled
