"""Session management models."""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    """Session status enumeration."""

    CREATED = "created"
    PROCESSING = "processing"
    TRANSCRIBED = "transcribed"
    SUMMARIZED = "summarized"
    EDITED = "edited"
    COMPLETED = "completed"
    EXPIRED = "expired"
    ERROR = "error"


class AudioMetadata(BaseModel):
    """Audio file metadata for session."""

    upload_id: str
    filename: str
    file_size: int
    mime_type: str
    duration_seconds: Optional[float] = None


class TranscriptionData(BaseModel):
    """Transcription results for session."""

    text: str
    language: str
    confidence: float
    processing_time_seconds: float


class DraftData(BaseModel):
    """Draft data for editing session."""

    transcription: Optional[str] = None
    summary: Optional[list[str]] = None
    keywords: Optional[list[str]] = None
    last_modified: datetime = Field(default_factory=datetime.utcnow)


class SessionState(BaseModel):
    """Complete session state model."""

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(hours=1)
    )
    status: SessionStatus = SessionStatus.CREATED

    # Processing data
    audio_metadata: Optional[AudioMetadata] = None
    transcription: Optional[TranscriptionData] = None
    summary: Optional[str] = None
    keywords: Optional[list[str]] = None
    user_edits: Optional[Dict[str, Any]] = None
    draft: Optional[DraftData] = None

    # Processing times
    transcription_time: Optional[float] = None
    summary_time: Optional[float] = None
    keyword_time: Optional[float] = None


class SessionCreateRequest(BaseModel):
    """Request model for creating session."""

    pass  # No parameters needed for initial creation


class SessionUpdateRequest(BaseModel):
    """Request model for updating session."""

    status: Optional[SessionStatus] = None
    user_edits: Optional[Dict[str, Any]] = None
    draft: Optional[DraftData] = None


class SessionResponse(BaseModel):
    """Response model for session operations."""

    session_id: str
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    audio_metadata: Optional[AudioMetadata] = None
    transcription: Optional[TranscriptionData] = None
    summary: Optional[str] = None
    keywords: Optional[list[str]] = None
    user_edits: Optional[Dict[str, Any]] = None
    draft: Optional[DraftData] = None
