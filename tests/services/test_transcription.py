"""Tests for transcription orchestration service."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

from app.services.transcription import TranscriptionService, transcription_service


class TestTranscriptionService:
    """Test cases for TranscriptionService."""

    def test_initialization(self):
        """Test service initialization."""
        service = TranscriptionService()
        assert service.max_concurrent == 2  # From settings default
        assert service.timeout_seconds == 300  # From settings default
        assert len(service._active_transcriptions) == 0

    @patch("app.services.transcription.settings")
    async def test_transcribe_upload_not_found(self, mock_settings):
        """Test transcription when upload directory doesn't exist."""
        mock_settings.upload_dir = Path("/tmp/nonexistent")

        service = TranscriptionService()

        with pytest.raises(HTTPException) as exc_info:
            await service.transcribe_upload("nonexistent-id")

        assert exc_info.value.status_code == 404
        assert "UPLOAD_NOT_FOUND" in str(exc_info.value.detail)

    @patch("app.services.transcription.settings")
    async def test_transcribe_upload_no_audio_file(self, mock_settings, tmp_path):
        """Test transcription when no audio file found."""
        upload_dir = tmp_path / "test-upload"
        upload_dir.mkdir()
        mock_settings.upload_dir = tmp_path

        service = TranscriptionService()

        with pytest.raises(HTTPException) as exc_info:
            await service.transcribe_upload("test-upload")

        assert exc_info.value.status_code == 404
        assert "AUDIO_FILE_NOT_FOUND" in str(exc_info.value.detail)

    @patch("app.services.transcription.whisper_manager")
    @patch("app.services.transcription.audio_converter")
    @patch("app.services.transcription.settings")
    async def test_transcribe_file_success(
        self, mock_settings, mock_converter, mock_whisper, tmp_path
    ):
        """Test successful file transcription."""
        # Setup mocks
        mock_settings.upload_dir = tmp_path

        mock_converter.get_audio_info.return_value = {
            "duration": 10.5,
            "format": "mp3",
            "sample_rate": 44100,
            "channels": 2,
        }
        mock_converter.is_conversion_needed.return_value = False

        mock_whisper.is_loaded = True
        mock_whisper.transcribe.return_value = {
            "text": "This is a test transcription",
            "language": "en",
            "duration": 10.5,
        }

        # Create test file
        upload_dir = tmp_path / "test-upload"
        upload_dir.mkdir()
        audio_file = upload_dir / "test.mp3"
        audio_file.write_text("fake audio data")

        service = TranscriptionService()
        result = await service.transcribe_file(audio_file, "test-upload")

        assert result["upload_id"] == "test-upload"
        assert result["transcription"]["text"] == "This is a test transcription"
        assert result["transcription"]["language"] == "en"
        assert result["transcription"]["duration_seconds"] == 10.5
        assert result["status"] == "completed"
        assert "processing_time_seconds" in result

    @patch("app.services.transcription.whisper_manager")
    @patch("app.services.transcription.audio_converter")
    async def test_transcribe_file_with_conversion(
        self, mock_converter, mock_whisper, tmp_path
    ):
        """Test transcription with audio format conversion."""
        # Setup mocks
        mock_converter.get_audio_info.return_value = {
            "duration": 10.5,
            "format": "mp3",
            "sample_rate": 44100,
            "channels": 2,
        }
        mock_converter.is_conversion_needed.return_value = True

        converted_file = tmp_path / "converted.wav"
        converted_file.write_text("converted audio")
        mock_converter.convert_to_whisper_format.return_value = (converted_file, 10.5)

        mock_whisper.is_loaded = True
        mock_whisper.transcribe.return_value = {
            "text": "Converted transcription",
            "language": "en",
        }

        # Create test file
        upload_dir = tmp_path / "test-upload"
        upload_dir.mkdir()
        audio_file = upload_dir / "test.mp3"
        audio_file.write_text("fake audio data")

        service = TranscriptionService()
        result = await service.transcribe_file(audio_file, "test-upload")

        assert result["transcription"]["text"] == "Converted transcription"
        mock_converter.convert_to_whisper_format.assert_called_once()

        # Verify converted file was cleaned up
        assert not converted_file.exists()

    @patch("app.services.transcription.whisper_manager")
    async def test_transcribe_file_model_not_loaded(self, mock_whisper, tmp_path):
        """Test transcription triggers model loading."""
        mock_whisper.is_loaded = False
        mock_whisper.is_loading = False
        mock_whisper.load_model = AsyncMock()

        # After loading, set as loaded
        async def mock_load():
            mock_whisper.is_loaded = True

        mock_whisper.load_model.side_effect = mock_load

        mock_whisper.transcribe.return_value = {
            "text": "Test after loading",
            "language": "en",
        }

        with patch("app.services.transcription.audio_converter") as mock_converter:
            mock_converter.get_audio_info.return_value = {"duration": 5.0}
            mock_converter.is_conversion_needed.return_value = False

            # Create test file
            upload_dir = tmp_path / "test-upload"
            upload_dir.mkdir()
            audio_file = upload_dir / "test.mp3"
            audio_file.write_text("fake audio data")

            service = TranscriptionService()
            result = await service.transcribe_file(audio_file, "test-upload")

            mock_whisper.load_model.assert_called_once()
            assert result["transcription"]["text"] == "Test after loading"

    @patch("app.services.transcription.whisper_manager")
    async def test_transcribe_file_timeout(self, mock_whisper, tmp_path):
        """Test transcription timeout handling."""
        mock_whisper.is_loaded = True

        # Mock transcription that takes too long
        async def slow_transcribe(*args, **kwargs):
            await asyncio.sleep(1)  # Longer than timeout
            return {"text": "Should not complete"}

        mock_whisper.transcribe.side_effect = slow_transcribe

        with patch("app.services.transcription.audio_converter") as mock_converter:
            mock_converter.get_audio_info.return_value = {"duration": 5.0}
            mock_converter.is_conversion_needed.return_value = False

            # Create test file
            upload_dir = tmp_path / "test-upload"
            upload_dir.mkdir()
            audio_file = upload_dir / "test.mp3"
            audio_file.write_text("fake audio data")

            service = TranscriptionService()
            service.timeout_seconds = 0.1  # Very short timeout

            with pytest.raises(HTTPException) as exc_info:
                await service.transcribe_file(audio_file, "test-upload")

            assert exc_info.value.status_code == 408
            assert "TRANSCRIPTION_TIMEOUT" in str(exc_info.value.detail)

    def test_calculate_confidence_with_segments(self):
        """Test confidence calculation with segment data."""
        service = TranscriptionService()

        whisper_result = {
            "text": "Test transcription",
            "segments": [
                {"avg_logprob": -0.2},
                {"avg_logprob": -0.4},
            ],
        }

        confidence = service._calculate_confidence(whisper_result)

        # Should be average of converted log probabilities
        expected = (0.8 + 0.6) / 2
        assert confidence == round(expected, 2)

    def test_calculate_confidence_without_segments(self):
        """Test confidence calculation without segment data."""
        service = TranscriptionService()

        # Long text should get higher confidence
        whisper_result = {
            "text": "This is a longer test transcription with many words",
            "segments": [],
        }

        confidence = service._calculate_confidence(whisper_result)
        assert confidence == 0.7  # For text with 5-20 words (has 9 words)

    def test_calculate_confidence_short_text(self):
        """Test confidence calculation for short text."""
        service = TranscriptionService()

        whisper_result = {"text": "Short", "segments": []}

        confidence = service._calculate_confidence(whisper_result)
        assert confidence == 0.6  # For text with less than 5 words (has 1 word)

    def test_calculate_confidence_empty_text(self):
        """Test confidence calculation for empty text."""
        service = TranscriptionService()

        whisper_result = {"text": "", "segments": []}

        confidence = service._calculate_confidence(whisper_result)
        assert confidence == 0.1  # Very low confidence for empty text

    async def test_get_transcription_status_active(self):
        """Test getting status of active transcription."""
        service = TranscriptionService()

        # Create a mock task
        mock_task = Mock()
        mock_task.done.return_value = False
        service._active_transcriptions["test-id"] = mock_task

        status = await service.get_transcription_status("test-id")

        assert status["upload_id"] == "test-id"
        assert status["status"] == "processing"
        assert not status["is_done"]

    async def test_get_transcription_status_completed(self):
        """Test getting status of completed transcription."""
        service = TranscriptionService()

        # Create a mock completed task
        mock_task = Mock()
        mock_task.done.return_value = True
        service._active_transcriptions["test-id"] = mock_task

        status = await service.get_transcription_status("test-id")

        assert status["upload_id"] == "test-id"
        assert status["status"] == "completed"
        assert status["is_done"]

    async def test_get_transcription_status_not_found(self):
        """Test getting status of non-existent transcription."""
        service = TranscriptionService()

        status = await service.get_transcription_status("nonexistent")

        assert status["upload_id"] == "nonexistent"
        assert status["status"] == "not_found"
        assert status["is_done"]

    async def test_cancel_transcription_success(self):
        """Test successful transcription cancellation."""
        service = TranscriptionService()

        # Create a mock active task
        mock_task = Mock()
        mock_task.done.return_value = False
        mock_task.cancel = Mock()
        service._active_transcriptions["test-id"] = mock_task

        result = await service.cancel_transcription("test-id")

        assert result is True
        mock_task.cancel.assert_called_once()

    async def test_cancel_transcription_not_found(self):
        """Test cancellation of non-existent transcription."""
        service = TranscriptionService()

        result = await service.cancel_transcription("nonexistent")

        assert result is False

    async def test_cancel_transcription_already_done(self):
        """Test cancellation of completed transcription."""
        service = TranscriptionService()

        # Create a mock completed task
        mock_task = Mock()
        mock_task.done.return_value = True
        service._active_transcriptions["test-id"] = mock_task

        result = await service.cancel_transcription("test-id")

        assert result is False

    @patch("app.services.transcription.whisper_manager")
    def test_get_service_status(self, mock_whisper):
        """Test getting service status."""
        mock_whisper.get_model_info.return_value = {
            "model_size": "base",
            "is_loaded": True,
        }

        service = TranscriptionService()
        service._active_transcriptions["test1"] = Mock()
        service._active_transcriptions["test2"] = Mock()

        status = service.get_service_status()

        assert status["max_concurrent"] == service.max_concurrent
        assert status["timeout_seconds"] == service.timeout_seconds
        assert status["active_transcriptions"] == 2
        assert "whisper_model" in status

    def test_global_instance(self):
        """Test global transcription_service instance."""
        assert isinstance(transcription_service, TranscriptionService)

    @patch("app.services.transcription.ollama_service")
    @patch("app.services.transcription.whisper_manager")
    @patch("app.services.transcription.audio_converter")
    @patch("app.services.transcription.settings")
    async def test_transcribe_file_with_summary_success(self, mock_settings, mock_converter, mock_whisper, mock_ollama, tmp_path):
        """Test successful transcription with summary generation."""
        # Setup mocks
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio data")
        
        mock_settings.upload_dir = tmp_path
        mock_converter.get_audio_info.return_value = {
            "duration": 30.0,
            "format": "wav",
            "sample_rate": 16000,
            "channels": 1
        }
        mock_converter.is_conversion_needed.return_value = False
        
        mock_whisper.is_loaded = True
        mock_whisper.is_loading = False
        mock_whisper.transcribe.return_value = {
            "text": "This is a test transcription about a project meeting with action items.",
            "language": "en",
            "segments": [{"avg_logprob": -0.5}]
        }
        
        mock_ollama.health_check.return_value = True
        mock_ollama.generate_summary.return_value = "- Project meeting discussed\n- Action items identified\n- Next steps planned"
        
        service = TranscriptionService()
        
        result = await service.transcribe_file(
            audio_file, "test-upload", None, include_summary=True, max_summary_words=100
        )
        
        # Verify transcription result
        assert result["upload_id"] == "test-upload"
        assert result["transcription"]["text"] == "This is a test transcription about a project meeting with action items."
        assert result["transcription"]["language"] == "en"
        assert result["status"] == "completed"
        
        # Verify summary was generated
        assert result["summary"] == "- Project meeting discussed\n- Action items identified\n- Next steps planned"
        assert result["summary_processing_time"] is not None
        assert result["summary_processing_time"] > 0
        
        # Verify service calls
        mock_ollama.health_check.assert_called_once()
        mock_ollama.generate_summary.assert_called_once_with(
            "This is a test transcription about a project meeting with action items.", 100
        )

    @patch("app.services.transcription.ollama_service")
    @patch("app.services.transcription.whisper_manager")
    @patch("app.services.transcription.audio_converter")
    @patch("app.services.transcription.settings")
    async def test_transcribe_file_with_summary_ollama_unavailable(self, mock_settings, mock_converter, mock_whisper, mock_ollama, tmp_path):
        """Test transcription with summary when Ollama service is unavailable."""
        # Setup mocks
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio data")
        
        mock_settings.upload_dir = tmp_path
        mock_converter.get_audio_info.return_value = {
            "duration": 30.0,
            "format": "wav",
            "sample_rate": 16000,
            "channels": 1
        }
        mock_converter.is_conversion_needed.return_value = False
        
        mock_whisper.is_loaded = True
        mock_whisper.is_loading = False
        mock_whisper.transcribe.return_value = {
            "text": "This is a test transcription.",
            "language": "en",
            "segments": [{"avg_logprob": -0.5}]
        }
        
        # Ollama service is unavailable
        mock_ollama.health_check.return_value = False
        
        service = TranscriptionService()
        
        result = await service.transcribe_file(
            audio_file, "test-upload", None, include_summary=True, max_summary_words=100
        )
        
        # Verify transcription succeeded but no summary
        assert result["upload_id"] == "test-upload"
        assert result["transcription"]["text"] == "This is a test transcription."
        assert result["summary"] is None
        assert result["summary_processing_time"] is None
        
        # Verify Ollama generate_summary was not called
        mock_ollama.health_check.assert_called_once()
        mock_ollama.generate_summary.assert_not_called()

    @patch("app.services.transcription.ollama_service")
    @patch("app.services.transcription.whisper_manager")
    @patch("app.services.transcription.audio_converter")
    @patch("app.services.transcription.settings")
    async def test_transcribe_file_with_summary_generation_fails(self, mock_settings, mock_converter, mock_whisper, mock_ollama, tmp_path):
        """Test transcription when summary generation fails gracefully."""
        # Setup mocks
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio data")
        
        mock_settings.upload_dir = tmp_path
        mock_converter.get_audio_info.return_value = {
            "duration": 30.0,
            "format": "wav",
            "sample_rate": 16000,
            "channels": 1
        }
        mock_converter.is_conversion_needed.return_value = False
        
        mock_whisper.is_loaded = True
        mock_whisper.is_loading = False
        mock_whisper.transcribe.return_value = {
            "text": "This is a test transcription.",
            "language": "en",
            "segments": [{"avg_logprob": -0.5}]
        }
        
        mock_ollama.health_check.return_value = True
        mock_ollama.generate_summary.side_effect = Exception("Summary generation failed")
        
        service = TranscriptionService()
        
        result = await service.transcribe_file(
            audio_file, "test-upload", None, include_summary=True, max_summary_words=100
        )
        
        # Verify transcription succeeded despite summary failure
        assert result["upload_id"] == "test-upload"
        assert result["transcription"]["text"] == "This is a test transcription."
        assert result["summary"] is None  # Should be None when generation fails
        assert result["summary_processing_time"] is None
        
        # Verify summary generation was attempted
        mock_ollama.health_check.assert_called_once()
        mock_ollama.generate_summary.assert_called_once()

    @patch("app.services.transcription.ollama_service")
    @patch("app.services.transcription.whisper_manager")
    @patch("app.services.transcription.audio_converter")
    @patch("app.services.transcription.settings")
    async def test_transcribe_file_without_summary(self, mock_settings, mock_converter, mock_whisper, mock_ollama, tmp_path):
        """Test transcription without summary (backward compatibility)."""
        # Setup mocks
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio data")
        
        mock_settings.upload_dir = tmp_path
        mock_converter.get_audio_info.return_value = {
            "duration": 30.0,
            "format": "wav",
            "sample_rate": 16000,
            "channels": 1
        }
        mock_converter.is_conversion_needed.return_value = False
        
        mock_whisper.is_loaded = True
        mock_whisper.is_loading = False
        mock_whisper.transcribe.return_value = {
            "text": "This is a test transcription.",
            "language": "en",
            "segments": [{"avg_logprob": -0.5}]
        }
        
        service = TranscriptionService()
        
        result = await service.transcribe_file(
            audio_file, "test-upload", None, include_summary=False
        )
        
        # Verify transcription result without summary fields
        assert result["upload_id"] == "test-upload"
        assert result["transcription"]["text"] == "This is a test transcription."
        assert "summary" not in result
        assert "summary_processing_time" not in result
        
        # Verify Ollama service was not called
        mock_ollama.health_check.assert_not_called()
        mock_ollama.generate_summary.assert_not_called()
