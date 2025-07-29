"""Tests for Whisper model management service."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from pathlib import Path

from app.services.whisper_model import WhisperModelManager, whisper_manager


class TestWhisperModelManager:
    """Test cases for WhisperModelManager."""

    def test_singleton_pattern(self):
        """Test that WhisperModelManager implements singleton pattern."""
        manager1 = WhisperModelManager()
        manager2 = WhisperModelManager()
        assert manager1 is manager2
        assert manager1 is whisper_manager

    def test_initial_state(self):
        """Test initial state of model manager."""
        manager = WhisperModelManager()
        assert not manager.is_loaded
        assert not manager.is_loading
        assert manager.load_error is None

    @patch("app.services.whisper_model.whisper.load_model")
    async def test_load_model_success(self, mock_load_model):
        """Test successful model loading."""
        mock_model = Mock()
        mock_load_model.return_value = mock_model
        
        manager = WhisperModelManager()
        # Reset any previous state
        manager._model = None
        manager._loading = False
        manager._load_error = None
        
        await manager.load_model()
        
        assert manager.is_loaded
        assert not manager.is_loading
        assert manager.load_error is None
        mock_load_model.assert_called_once()

    @patch("app.services.whisper_model.whisper.load_model")
    async def test_load_model_failure(self, mock_load_model):
        """Test model loading failure."""
        mock_load_model.side_effect = Exception("Model load failed")
        
        manager = WhisperModelManager()
        # Reset any previous state
        manager._model = None
        manager._loading = False
        manager._load_error = None
        
        with pytest.raises(RuntimeError, match="Failed to load Whisper model"):
            await manager.load_model()
        
        assert not manager.is_loaded
        assert not manager.is_loading
        assert "Model load failed" in manager.load_error

    @patch("app.services.whisper_model.whisper.load_model")
    async def test_load_model_already_loaded(self, mock_load_model):
        """Test that model is not loaded if already loaded."""
        mock_model = Mock()
        manager = WhisperModelManager()
        manager._model = mock_model
        
        await manager.load_model()
        
        mock_load_model.assert_not_called()
        assert manager.is_loaded

    async def test_transcribe_without_model(self):
        """Test transcription without loaded model."""
        manager = WhisperModelManager()
        manager._model = None
        
        with pytest.raises(RuntimeError, match="Whisper model not loaded"):
            await manager.transcribe("test.wav")

    @patch("app.services.whisper_model.whisper.load_model")
    async def test_transcribe_success(self, mock_load_model):
        """Test successful transcription."""
        mock_result = {
            "text": "This is a test transcription",
            "language": "en",
            "duration": 5.0,
            "segments": [
                {"text": "This is a test", "start": 0.0, "end": 2.5},
                {"text": " transcription", "start": 2.5, "end": 5.0},
            ],
        }
        
        mock_model = Mock()
        mock_model.transcribe.return_value = mock_result
        mock_load_model.return_value = mock_model
        
        manager = WhisperModelManager()
        manager._model = mock_model
        
        result = await manager.transcribe("test.wav", language="en")
        
        assert result == mock_result
        mock_model.transcribe.assert_called_once_with(
            audio="test.wav",
            language="en",
            task="transcribe",
            fp16=False,
            verbose=False,
        )

    @patch("app.services.whisper_model.whisper.load_model")
    async def test_transcribe_failure(self, mock_load_model):
        """Test transcription failure."""
        mock_model = Mock()
        mock_model.transcribe.side_effect = Exception("Transcription failed")
        mock_load_model.return_value = mock_model
        
        manager = WhisperModelManager()
        manager._model = mock_model
        
        with pytest.raises(RuntimeError, match="Transcription failed"):
            await manager.transcribe("test.wav")

    def test_get_model_info(self):
        """Test getting model information."""
        manager = WhisperModelManager()
        manager._model = None
        manager._loading = False
        manager._load_error = "Test error"
        
        info = manager.get_model_info()
        
        expected_info = {
            "model_size": manager._model_size,
            "device": manager._device,
            "compute_type": manager._compute_type,
            "is_loaded": False,
            "is_loading": False,
            "load_error": "Test error",
        }
        
        assert info == expected_info

    @patch("app.services.whisper_model.whisper.load_model")
    async def test_transcribe_with_custom_params(self, mock_load_model):
        """Test transcription with custom parameters."""
        mock_result = {"text": "Test", "language": "es"}
        mock_model = Mock()
        mock_model.transcribe.return_value = mock_result
        mock_load_model.return_value = mock_model
        
        manager = WhisperModelManager()
        manager._model = mock_model
        
        result = await manager.transcribe(
            "test.wav", 
            language="es", 
            task="translate"
        )
        
        assert result == mock_result
        mock_model.transcribe.assert_called_once_with(
            audio="test.wav",
            language="es",
            task="translate",
            fp16=False,
            verbose=False,
        )

    async def test_concurrent_loading(self):
        """Test that concurrent load attempts don't cause issues."""
        import asyncio
        
        manager = WhisperModelManager()
        manager._model = None
        manager._loading = False
        
        with patch("app.services.whisper_model.whisper.load_model") as mock_load:
            mock_load.return_value = Mock()
            
            # Start multiple load operations concurrently
            tasks = [manager.load_model() for _ in range(3)]
            await asyncio.gather(*tasks)
            
            # Model should only be loaded once
            assert mock_load.call_count == 1
            assert manager.is_loaded