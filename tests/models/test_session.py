"""Tests for session models."""

import pytest
from datetime import datetime, timedelta
from uuid import UUID

from app.models.session import (
    SessionState,
    SessionStatus,
    AudioMetadata,
    TranscriptionData,
    SessionCreateRequest,
    SessionUpdateRequest,
    SessionResponse,
)


class TestSessionModels:
    """Test session model validation and behavior."""

    def test_session_state_defaults(self):
        """Test SessionState creates with proper defaults."""
        session = SessionState()
        
        assert isinstance(session.session_id, str)
        assert UUID(session.session_id)  # Valid UUID format
        assert session.status == SessionStatus.CREATED
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.updated_at, datetime)
        assert isinstance(session.expires_at, datetime)
        assert session.expires_at > session.created_at
        assert session.audio_metadata is None
        assert session.transcription is None
        assert session.summary is None
        assert session.keywords is None
        assert session.user_edits is None

    def test_session_state_with_data(self):
        """Test SessionState with complete data."""
        audio_meta = AudioMetadata(
            upload_id="test_upload_123",
            filename="test_audio.webm",
            file_size=1024000,
            mime_type="audio/webm",
            duration_seconds=30.5,
        )
        
        transcription = TranscriptionData(
            text="This is a test transcription.",
            language="en",
            confidence=0.95,
            processing_time_seconds=2.3,
        )
        
        session = SessionState(
            status=SessionStatus.TRANSCRIBED,
            audio_metadata=audio_meta,
            transcription=transcription,
            summary="Test summary content",
            keywords=["test", "transcription", "audio"],
            transcription_time=2.3,
        )
        
        assert session.status == SessionStatus.TRANSCRIBED
        assert session.audio_metadata == audio_meta
        assert session.transcription == transcription
        assert session.summary == "Test summary content"
        assert session.keywords == ["test", "transcription", "audio"]
        assert session.transcription_time == 2.3

    def test_audio_metadata_validation(self):
        """Test AudioMetadata validation."""
        metadata = AudioMetadata(
            upload_id="upload_123",
            filename="audio.mp3",
            file_size=2048000,
            mime_type="audio/mpeg",
        )
        
        assert metadata.upload_id == "upload_123"
        assert metadata.filename == "audio.mp3"
        assert metadata.file_size == 2048000
        assert metadata.mime_type == "audio/mpeg"
        assert metadata.duration_seconds is None

    def test_transcription_data_validation(self):
        """Test TranscriptionData validation."""
        transcription = TranscriptionData(
            text="Hello world",
            language="en",
            confidence=0.98,
            processing_time_seconds=1.5,
        )
        
        assert transcription.text == "Hello world"
        assert transcription.language == "en"
        assert transcription.confidence == 0.98
        assert transcription.processing_time_seconds == 1.5

    def test_session_status_enum(self):
        """Test SessionStatus enum values."""
        assert SessionStatus.CREATED == "created"
        assert SessionStatus.PROCESSING == "processing"
        assert SessionStatus.TRANSCRIBED == "transcribed"
        assert SessionStatus.SUMMARIZED == "summarized"
        assert SessionStatus.EDITED == "edited"
        assert SessionStatus.COMPLETED == "completed"
        assert SessionStatus.EXPIRED == "expired"
        assert SessionStatus.ERROR == "error"

    def test_session_create_request(self):
        """Test SessionCreateRequest model."""
        request = SessionCreateRequest()
        # Should be empty model for initial creation
        assert request.model_dump() == {}

    def test_session_update_request(self):
        """Test SessionUpdateRequest model."""
        request = SessionUpdateRequest(
            status=SessionStatus.EDITED,
            user_edits={"notes": "Additional notes"},
        )
        
        assert request.status == SessionStatus.EDITED
        assert request.user_edits == {"notes": "Additional notes"}

    def test_session_response_model(self):
        """Test SessionResponse model."""
        session_data = SessionState()
        response = SessionResponse(**session_data.model_dump())
        
        assert response.session_id == session_data.session_id
        assert response.status == session_data.status
        assert response.created_at == session_data.created_at
        assert response.updated_at == session_data.updated_at
        assert response.expires_at == session_data.expires_at