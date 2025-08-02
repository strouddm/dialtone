"""Integration tests for session workflow."""

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from app.models.session import SessionState, SessionStatus
from app.services.session_manager import SessionManager
from app.services.session_storage import SessionStorage


@pytest.fixture
def temp_storage_dir(tmp_path):
    """Create temporary storage directory for integration tests."""
    storage_dir = tmp_path / "sessions"
    storage_dir.mkdir()
    return storage_dir


@pytest.fixture
def integration_setup(temp_storage_dir):
    """Setup for integration tests."""
    with patch("app.services.session_storage.settings") as mock_settings:
        mock_settings.session_storage_dir = temp_storage_dir
        mock_settings.session_timeout_hours = 1

        storage = SessionStorage()
        manager = SessionManager()

        # Replace global instances
        with patch("app.services.session_manager.session_storage", storage):
            yield manager, storage


class TestSessionWorkflowIntegration:
    """Integration tests for complete session workflows."""

    @pytest.mark.asyncio
    async def test_complete_session_lifecycle(self, integration_setup):
        """Test complete session lifecycle from creation to deletion."""
        manager, storage = integration_setup

        # 1. Create session
        session_id = await manager.create_session()
        assert session_id

        # 2. Verify session exists and is valid
        session_state = await manager.get_session_state(session_id)
        assert session_state.status == SessionStatus.CREATED
        assert session_state.session_id == session_id

        # 3. Update session with audio metadata
        from app.models.session import AudioMetadata

        audio_metadata = AudioMetadata(
            upload_id="test_upload_123",
            filename="test_audio.webm",
            file_size=1024000,
            mime_type="audio/webm",
        )

        updated_session = await manager.update_session_data(
            session_id,
            audio_metadata=audio_metadata,
            status=SessionStatus.PROCESSING,
        )

        assert updated_session.status == SessionStatus.PROCESSING
        assert updated_session.audio_metadata.upload_id == "test_upload_123"

        # 4. Add transcription results
        from app.models.session import TranscriptionData

        transcription = TranscriptionData(
            text="This is a test transcription",
            language="en",
            confidence=0.95,
            processing_time_seconds=2.5,
        )

        updated_session = await manager.update_session_data(
            session_id,
            transcription=transcription,
            status=SessionStatus.TRANSCRIBED,
            transcription_time=2.5,
        )

        assert updated_session.status == SessionStatus.TRANSCRIBED
        assert updated_session.transcription.text == "This is a test transcription"

        # 5. Add summary and keywords
        updated_session = await manager.update_session_data(
            session_id,
            summary="Test summary of the transcription",
            keywords=["test", "transcription", "audio"],
            status=SessionStatus.SUMMARIZED,
        )

        assert updated_session.status == SessionStatus.SUMMARIZED
        assert updated_session.summary == "Test summary of the transcription"
        assert updated_session.keywords == ["test", "transcription", "audio"]

        # 6. Add user edits
        user_edits = {
            "title": "Edited Test Note",
            "additional_notes": "User added some notes",
        }

        updated_session = await manager.update_session_data(
            session_id,
            user_edits=user_edits,
            status=SessionStatus.EDITED,
        )

        assert updated_session.status == SessionStatus.EDITED
        assert updated_session.user_edits == user_edits

        # 7. Complete session
        final_session = await manager.update_session_data(
            session_id,
            status=SessionStatus.COMPLETED,
        )

        assert final_session.status == SessionStatus.COMPLETED

        # 8. Verify persistence - retrieve fresh session
        persisted_session = await manager.get_session_state(session_id)
        assert persisted_session.status == SessionStatus.COMPLETED
        assert persisted_session.transcription.text == "This is a test transcription"
        assert persisted_session.summary == "Test summary of the transcription"
        assert persisted_session.user_edits == user_edits

        # 9. Delete session
        deleted = await storage.delete_session(session_id)
        assert deleted is True

        # 10. Verify session is gone
        missing_session = await storage.get_session(session_id)
        assert missing_session is None

    @pytest.mark.asyncio
    async def test_session_expiration_workflow(self, integration_setup):
        """Test session expiration and cleanup workflow."""
        from datetime import datetime, timedelta

        manager, storage = integration_setup

        # Create session
        session_id = await manager.create_session()

        # Manually expire session
        session = await storage.get_session(session_id)
        session.expires_at = datetime.utcnow() - timedelta(hours=1)
        await storage.save_session(session)

        # Try to access expired session
        from app.services.session_manager import SessionExpiredError

        with pytest.raises(SessionExpiredError):
            await manager.get_session_state(session_id)

        # Run cleanup
        cleanup_count = await manager.cleanup_expired_sessions()
        assert cleanup_count == 1

        # Verify session is deleted
        missing_session = await storage.get_session(session_id)
        assert missing_session is None

    @pytest.mark.asyncio
    async def test_concurrent_session_operations(self, integration_setup):
        """Test concurrent operations on multiple sessions."""
        manager, storage = integration_setup

        # Create multiple sessions concurrently
        session_tasks = [manager.create_session() for _ in range(5)]
        session_ids = await asyncio.gather(*session_tasks)

        assert len(session_ids) == 5
        assert len(set(session_ids)) == 5  # All unique

        # Concurrent updates
        async def update_session_workflow(session_id, index):
            await manager.update_session_data(
                session_id,
                status=SessionStatus.PROCESSING,
                summary=f"Summary for session {index}",
            )
            return await manager.get_session_state(session_id)

        update_tasks = [
            update_session_workflow(session_id, i)
            for i, session_id in enumerate(session_ids)
        ]

        updated_sessions = await asyncio.gather(*update_tasks)

        # Verify all updates were successful
        for i, session in enumerate(updated_sessions):
            assert session.status == SessionStatus.PROCESSING
            assert session.summary == f"Summary for session {i}"

        # Cleanup all sessions
        cleanup_tasks = [
            storage.delete_session(session_id) for session_id in session_ids
        ]
        cleanup_results = await asyncio.gather(*cleanup_tasks)

        assert all(cleanup_results)

    @pytest.mark.asyncio
    async def test_session_validation_workflow(self, integration_setup):
        """Test session validation in various states."""
        manager, storage = integration_setup

        # Create valid session
        session_id = await manager.create_session()

        # Should be valid initially
        is_valid = await manager.validate_session(session_id)
        assert is_valid is True

        # Should be invalid for non-existent session
        is_valid = await manager.validate_session("nonexistent_session")
        assert is_valid is False

        # Make session expired
        session = await storage.get_session(session_id)
        session.expires_at = datetime.utcnow() - timedelta(minutes=1)
        await storage.save_session(session)

        # Should be invalid for expired session
        is_valid = await manager.validate_session(session_id)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_session_extension_workflow(self, integration_setup):
        """Test session extension workflow."""
        from datetime import datetime, timedelta

        manager, storage = integration_setup

        # Create session
        session_id = await manager.create_session()
        original_session = await manager.get_session_state(session_id)
        original_expires = original_session.expires_at

        # Extend session
        extended_session = await manager.extend_session(session_id, hours=2)

        # Verify extension
        assert extended_session.expires_at > original_expires
        time_diff = extended_session.expires_at - original_expires
        assert time_diff >= timedelta(
            hours=1, minutes=59
        )  # Account for processing time

        # Verify persistence
        persisted_session = await storage.get_session(session_id)
        assert persisted_session.expires_at == extended_session.expires_at

    @pytest.mark.asyncio
    async def test_session_error_recovery(self, integration_setup):
        """Test error recovery in session operations."""
        manager, storage = integration_setup

        # Create session
        session_id = await manager.create_session()

        # Test recovery from storage errors
        with patch.object(
            storage, "save_session", side_effect=Exception("Storage error")
        ):
            # Should raise the storage error
            with pytest.raises(Exception):
                await manager.update_session_data(session_id, summary="Test")

        # Session should still be accessible after error
        session = await manager.get_session_state(session_id)
        assert session.session_id == session_id

        # Should be able to update after error recovery
        updated_session = await manager.update_session_data(
            session_id,
            summary="Recovered update",
        )
        assert updated_session.summary == "Recovered update"
