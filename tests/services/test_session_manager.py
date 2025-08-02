"""Tests for session manager service."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.models.session import SessionState, SessionStatus
from app.services.session_manager import (
    SessionExpiredError,
    SessionManager,
    SessionNotFoundError,
)


@pytest.fixture
def mock_storage():
    """Mock session storage."""
    with patch("app.services.session_manager.session_storage") as mock:
        yield mock


@pytest.fixture
def session_manager():
    """Create SessionManager instance."""
    return SessionManager()


class TestSessionManager:
    """Test session manager operations."""

    @pytest.mark.asyncio
    async def test_create_session(self, session_manager, mock_storage):
        """Test creating a new session."""
        # Mock storage to return session
        mock_session = SessionState()
        mock_storage.create_session.return_value = mock_session

        session_id = await session_manager.create_session()

        assert session_id == mock_session.session_id
        mock_storage.create_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session_state_valid(self, session_manager, mock_storage):
        """Test getting valid session state."""
        session_id = "test_session_123"
        mock_session = SessionState(
            session_id=session_id,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        mock_storage.get_session.return_value = mock_session

        result = await session_manager.get_session_state(session_id)

        assert result == mock_session
        mock_storage.get_session.assert_called_once_with(session_id)

    @pytest.mark.asyncio
    async def test_get_session_state_not_found(self, session_manager, mock_storage):
        """Test getting non-existent session."""
        session_id = "nonexistent_session"
        mock_storage.get_session.return_value = None

        with pytest.raises(SessionNotFoundError):
            await session_manager.get_session_state(session_id)

    @pytest.mark.asyncio
    async def test_get_session_state_expired(self, session_manager, mock_storage):
        """Test getting expired session."""
        session_id = "expired_session"
        mock_session = SessionState(
            session_id=session_id,
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        mock_storage.get_session.return_value = mock_session

        with pytest.raises(SessionExpiredError):
            await session_manager.get_session_state(session_id)

        # Should have updated session status to expired
        mock_storage.save_session.assert_called_once()
        assert mock_session.status == SessionStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_update_session_data(self, session_manager, mock_storage):
        """Test updating session data."""
        session_id = "test_session_123"
        mock_session = SessionState(
            session_id=session_id,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        mock_storage.get_session.return_value = mock_session

        # Update session
        result = await session_manager.update_session_data(
            session_id,
            status=SessionStatus.PROCESSING,
            summary="Test summary",
        )

        assert result.status == SessionStatus.PROCESSING
        assert result.summary == "Test summary"
        mock_storage.save_session.assert_called_once_with(mock_session)

    @pytest.mark.asyncio
    async def test_validate_session_valid(self, session_manager, mock_storage):
        """Test validating valid session."""
        session_id = "valid_session"
        mock_session = SessionState(
            session_id=session_id,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        mock_storage.get_session.return_value = mock_session

        result = await session_manager.validate_session(session_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_session_invalid(self, session_manager, mock_storage):
        """Test validating invalid session."""
        mock_storage.get_session.return_value = None

        result = await session_manager.validate_session("invalid_session")
        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, session_manager, mock_storage):
        """Test cleaning up expired sessions."""
        expired_sessions = ["session1", "session2", "session3"]
        mock_storage.list_expired_sessions.return_value = expired_sessions
        mock_storage.delete_session.return_value = True

        cleanup_count = await session_manager.cleanup_expired_sessions()

        assert cleanup_count == 3
        assert mock_storage.delete_session.call_count == 3

    @pytest.mark.asyncio
    async def test_cleanup_with_failures(self, session_manager, mock_storage):
        """Test cleanup with some failures."""
        expired_sessions = ["session1", "session2", "session3"]
        mock_storage.list_expired_sessions.return_value = expired_sessions

        # Mock some deletions to fail
        def delete_side_effect(session_id):
            if session_id == "session2":
                raise Exception("Delete failed")
            return True

        mock_storage.delete_session.side_effect = delete_side_effect

        cleanup_count = await session_manager.cleanup_expired_sessions()

        assert cleanup_count == 2  # Only 2 successful deletions

    @pytest.mark.asyncio
    async def test_extend_session(self, session_manager, mock_storage):
        """Test extending session expiration."""
        session_id = "test_session"
        original_expires = datetime.utcnow() + timedelta(minutes=30)
        mock_session = SessionState(
            session_id=session_id,
            expires_at=original_expires,
        )
        mock_storage.get_session.return_value = mock_session

        result = await session_manager.extend_session(session_id, hours=2)

        assert result.expires_at > original_expires
        mock_storage.save_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_session_data_none_values(self, session_manager, mock_storage):
        """Test updating session data with None values."""
        session_id = "test_session"
        mock_session = SessionState(
            session_id=session_id,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        mock_storage.get_session.return_value = mock_session

        # Update with None values (should be ignored)
        await session_manager.update_session_data(
            session_id,
            status=SessionStatus.PROCESSING,
            summary=None,  # Should be ignored
            keywords=["test"],
        )

        assert mock_session.status == SessionStatus.PROCESSING
        assert mock_session.summary is None  # Should remain None
        assert mock_session.keywords == ["test"]

    @pytest.mark.asyncio
    async def test_update_session_data_invalid_attributes(
        self, session_manager, mock_storage
    ):
        """Test updating session with invalid attributes."""
        session_id = "test_session"
        mock_session = SessionState(
            session_id=session_id,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        mock_storage.get_session.return_value = mock_session

        # Update with invalid attribute (should be ignored)
        await session_manager.update_session_data(
            session_id,
            invalid_field="should_be_ignored",
            status=SessionStatus.PROCESSING,
        )

        assert mock_session.status == SessionStatus.PROCESSING
        assert not hasattr(mock_session, "invalid_field")
