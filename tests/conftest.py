"""Common test fixtures and configuration for integration tests."""

import os
import json
import pytest
import asyncio
from pathlib import Path
from typing import AsyncGenerator, Dict, Any
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import create_app
from app.core.settings import settings
from app.models.session import SessionState, SessionStatus


# Set testing environment
os.environ["TESTING"] = "true"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client():
    """Create test client for synchronous tests."""
    app = create_app()
    return TestClient(app)


@pytest.fixture(scope="session")
async def integration_test_app():
    """FastAPI test app with full service stack for integration tests."""
    app = create_app()
    return app


@pytest.fixture
async def async_client(integration_test_app) -> AsyncGenerator[AsyncClient, None]:
    """Async client for integration tests."""
    async with AsyncClient(app=integration_test_app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_audio_files() -> Dict[str, Path]:
    """Collection of test audio files in different formats."""
    # For now, return mock paths - will be replaced with actual audio samples
    test_files_dir = Path(__file__).parent / "fixtures" / "audio_samples"
    
    return {
        "short_webm": test_files_dir / "short_sample.webm",
        "medium_m4a": test_files_dir / "medium_sample.m4a", 
        "long_mp3": test_files_dir / "long_sample.mp3",
        "poor_quality": test_files_dir / "poor_quality.webm"
    }


@pytest.fixture
async def test_obsidian_vault(tmp_path) -> Path:
    """Temporary Obsidian vault for testing."""
    vault_path = tmp_path / "test_vault"
    vault_path.mkdir(parents=True, exist_ok=True)
    
    # Create basic Obsidian vault structure
    (vault_path / ".obsidian").mkdir(exist_ok=True)
    (vault_path / "Daily Notes").mkdir(exist_ok=True)
    (vault_path / "Voice Notes").mkdir(exist_ok=True)
    
    return vault_path


@pytest.fixture
def mock_whisper_service():
    """Mock Whisper transcription service."""
    with patch("app.services.whisper_model.WhisperModel") as mock:
        mock_instance = AsyncMock()
        mock_instance.transcribe.return_value = {
            "text": "This is a test transcription from the mock Whisper service.",
            "segments": [
                {
                    "start": 0.0,
                    "end": 3.5,
                    "text": "This is a test transcription"
                },
                {
                    "start": 3.5,
                    "end": 6.0,
                    "text": "from the mock Whisper service."
                }
            ]
        }
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_ollama_service():
    """Mock Ollama summarization service."""
    with patch("app.services.ollama.OllamaService") as mock:
        mock_instance = AsyncMock()
        mock_instance.summarize.return_value = {
            "summary": "- Test transcription completed successfully\n- Mock service integration verified",
            "keywords": ["test", "transcription", "mock", "integration"]
        }
        mock_instance.is_healthy.return_value = True
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_session_manager():
    """Mock session manager for testing."""
    with patch("app.services.session_manager.SessionManager") as mock:
        mock_instance = AsyncMock()
        mock_instance.create_session.return_value = "test_session_123"
        mock_instance.get_session_state.return_value = SessionState(
            session_id="test_session_123",
            status=SessionStatus.CREATED
        )
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def test_audio_content() -> bytes:
    """Mock audio content for testing."""
    # Return dummy binary content representing an audio file
    return b'\x00\x01\x02\x03' * 1000  # 4KB of dummy audio data


@pytest.fixture
def test_transcription_data() -> Dict[str, Any]:
    """Standard test transcription data."""
    return {
        "text": "This is a comprehensive test transcription that includes multiple sentences. It covers various aspects of speech recognition including punctuation, capitalization, and natural speech patterns. The transcription service should handle this content effectively.",
        "segments": [
            {
                "start": 0.0,
                "end": 4.2,
                "text": "This is a comprehensive test transcription that includes multiple sentences."
            },
            {
                "start": 4.2,
                "end": 8.1,
                "text": "It covers various aspects of speech recognition including punctuation, capitalization, and natural speech patterns."
            },
            {
                "start": 8.1,
                "end": 10.5,
                "text": "The transcription service should handle this content effectively."
            }
        ]
    }


@pytest.fixture
def test_summary_data() -> Dict[str, Any]:
    """Standard test summary data."""
    return {
        "summary": "- Comprehensive test transcription analysis\n- Multiple sentence structure verification\n- Speech recognition accuracy assessment\n- Punctuation and capitalization handling\n- Natural speech pattern processing",
        "keywords": ["transcription", "speech", "recognition", "analysis", "testing"]
    }


@pytest.fixture
def test_session_state() -> SessionState:
    """Standard test session state."""
    return SessionState(
        session_id="integration_test_session",
        status=SessionStatus.CREATED,
        upload_id="integration_test_upload",
        transcription="Test transcription content",
        summary="- Test summary point\n- Integration test verified",
        keywords=["integration", "test", "session"]
    )


@pytest.fixture(autouse=True)
def setup_test_environment(tmp_path):
    """Setup test environment with temporary directories."""
    # Create test directories
    test_upload_dir = tmp_path / "uploads"
    test_session_dir = tmp_path / "sessions"
    test_vault_dir = tmp_path / "vault"
    
    test_upload_dir.mkdir(exist_ok=True)
    test_session_dir.mkdir(exist_ok=True)
    test_vault_dir.mkdir(exist_ok=True)
    
    # Patch settings for testing
    with patch.object(settings, 'upload_dir', test_upload_dir), \
         patch.object(settings, 'session_storage_dir', test_session_dir), \
         patch.object(settings, 'obsidian_vault_path', test_vault_dir):
        yield {
            "upload_dir": test_upload_dir,
            "session_dir": test_session_dir,
            "vault_dir": test_vault_dir
        }


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "benchmark: mark test as performance benchmark"
    )


# Collection hook to organize test execution
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Add integration marker to tests in integration directory
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        
        # Add slow marker to performance tests
        if "performance" in str(item.fspath) or "benchmark" in item.name:
            item.add_marker(pytest.mark.slow)
            item.add_marker(pytest.mark.benchmark)