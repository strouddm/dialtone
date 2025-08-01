"""Tests for session storage service."""

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch, mock_open

from app.models.session import SessionState, SessionStatus
from app.services.session_storage import SessionStorage, SessionStorageError


@pytest.fixture
def temp_storage_dir(tmp_path):
    """Create temporary storage directory for tests."""
    storage_dir = tmp_path / "sessions"
    storage_dir.mkdir()
    return storage_dir


@pytest.fixture
def storage_service(temp_storage_dir):
    """Create SessionStorage instance with temp directory."""
    with patch("app.services.session_storage.settings") as mock_settings:
        mock_settings.session_storage_dir = temp_storage_dir
        storage = SessionStorage()
        return storage


class TestSessionStorage:
    """Test session storage operations."""

    @pytest.mark.asyncio
    async def test_create_session(self, storage_service):
        """Test creating a new session."""
        session = await storage_service.create_session()
        
        assert isinstance(session, SessionState)
        assert session.status == SessionStatus.CREATED
        assert session.session_id
        
        # Verify file was created
        session_file = storage_service._get_session_path(session.session_id)
        assert session_file.exists()

    @pytest.mark.asyncio
    async def test_get_session_existing(self, storage_service):
        """Test retrieving existing session."""
        # Create session
        original_session = await storage_service.create_session()
        
        # Retrieve session
        retrieved_session = await storage_service.get_session(original_session.session_id)
        
        assert retrieved_session is not None
        assert retrieved_session.session_id == original_session.session_id
        assert retrieved_session.status == original_session.status

    @pytest.mark.asyncio
    async def test_get_session_nonexistent(self, storage_service):
        """Test retrieving non-existent session."""
        result = await storage_service.get_session("nonexistent_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_save_session(self, storage_service):
        """Test saving session updates."""
        session = SessionState()
        await storage_service.save_session(session)
        
        # Modify session
        session.status = SessionStatus.PROCESSING
        session.summary = "Test summary"
        await storage_service.save_session(session)
        
        # Retrieve and verify
        retrieved = await storage_service.get_session(session.session_id)
        assert retrieved.status == SessionStatus.PROCESSING
        assert retrieved.summary == "Test summary"
        assert retrieved.updated_at != retrieved.created_at

    @pytest.mark.asyncio
    async def test_delete_session_existing(self, storage_service):
        """Test deleting existing session."""
        session = await storage_service.create_session()
        session_id = session.session_id
        
        # Verify session exists
        assert await storage_service.get_session(session_id) is not None
        
        # Delete session
        result = await storage_service.delete_session(session_id)
        assert result is True
        
        # Verify session is gone
        assert await storage_service.get_session(session_id) is None

    @pytest.mark.asyncio
    async def test_delete_session_nonexistent(self, storage_service):
        """Test deleting non-existent session."""
        result = await storage_service.delete_session("nonexistent_id")
        assert result is False

    @pytest.mark.asyncio
    async def test_list_expired_sessions(self, storage_service):
        """Test listing expired sessions."""
        # Create fresh session
        fresh_session = await storage_service.create_session()
        
        # Create expired session
        expired_session = SessionState()
        expired_session.expires_at = datetime.utcnow() - timedelta(hours=1)
        await storage_service.save_session(expired_session)
        
        # Get expired sessions
        expired_ids = await storage_service.list_expired_sessions()
        
        assert expired_session.session_id in expired_ids
        assert fresh_session.session_id not in expired_ids

    @pytest.mark.asyncio
    async def test_concurrent_session_access(self, storage_service):
        """Test concurrent access to same session."""
        session = await storage_service.create_session()
        session_id = session.session_id
        
        async def update_session(suffix):
            session_data = await storage_service.get_session(session_id)
            session_data.summary = f"Summary {suffix}"
            await storage_service.save_session(session_data)
        
        # Run concurrent updates
        await asyncio.gather(
            update_session("A"),
            update_session("B"),
            update_session("C"),
        )
        
        # Verify session still exists and is valid
        final_session = await storage_service.get_session(session_id)
        assert final_session is not None
        assert final_session.summary.startswith("Summary ")

    @pytest.mark.asyncio
    async def test_storage_error_handling(self, storage_service):
        """Test error handling in storage operations."""
        session_id = "test_session_123"
        
        # Mock file operations to raise exceptions
        with patch("aiofiles.open", side_effect=OSError("Disk full")):
            session = SessionState(session_id=session_id)
            
            with pytest.raises(SessionStorageError):
                await storage_service.save_session(session)

    @pytest.mark.asyncio
    async def test_corrupted_session_file(self, storage_service, temp_storage_dir):
        """Test handling corrupted session files."""
        # Create corrupted session file
        corrupted_file = temp_storage_dir / "corrupted_session.json"
        corrupted_file.write_text("invalid json content")
        
        # Should handle corrupted files gracefully in list_expired_sessions
        expired_sessions = await storage_service.list_expired_sessions()
        # Should not crash and return empty list or valid sessions only
        assert isinstance(expired_sessions, list)

    @pytest.mark.asyncio
    async def test_session_file_path(self, storage_service):
        """Test session file path generation."""
        session_id = "test_session_123"
        path = storage_service._get_session_path(session_id)
        
        assert isinstance(path, Path)
        assert path.name == f"{session_id}.json"
        assert path.parent == storage_service.storage_dir

    @pytest.mark.asyncio
    async def test_lock_management(self, storage_service):
        """Test session lock management."""
        session_id = "test_session_123"
        
        # Get lock multiple times
        lock1 = await storage_service._get_lock(session_id)
        lock2 = await storage_service._get_lock(session_id)
        
        # Should return same lock instance
        assert lock1 is lock2
        assert isinstance(lock1, asyncio.Lock)