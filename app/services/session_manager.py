"""Session management service."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from app.core.exceptions import NotFoundError, ValidationError
from app.core.settings import settings
from app.models.session import SessionState, SessionStatus
from app.services.session_storage import SessionStorageError, session_storage

logger = logging.getLogger(__name__)


class SessionNotFoundError(NotFoundError):
    """Session not found error."""

    pass


class SessionExpiredError(ValidationError):
    """Session expired error."""

    pass


class SessionManager:
    """Session management service."""

    async def create_session(self) -> str:
        """Create new session and return session ID."""
        try:
            session = await session_storage.create_session()

            logger.info(
                "Session created",
                extra={
                    "session_id": session.session_id,
                    "expires_at": session.expires_at.isoformat(),
                },
            )

            return session.session_id

        except SessionStorageError as e:
            logger.error(f"Failed to create session: {e}")
            raise

    async def get_session_state(self, session_id: str) -> SessionState:
        """Get session state with validation."""
        session = await session_storage.get_session(session_id)

        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        # Check expiration
        if session.expires_at < datetime.utcnow():
            session.status = SessionStatus.EXPIRED
            await session_storage.save_session(session)
            raise SessionExpiredError(f"Session {session_id} has expired")

        return session

    async def update_session_data(self, session_id: str, **kwargs) -> SessionState:
        """Update session with new data."""
        session = await self.get_session_state(session_id)

        # Update allowed fields
        for key, value in kwargs.items():
            if hasattr(session, key) and value is not None:
                setattr(session, key, value)

        await session_storage.save_session(session)

        logger.info(
            "Session updated",
            extra={
                "session_id": session_id,
                "updated_fields": list(kwargs.keys()),
            },
        )

        return session

    async def validate_session(self, session_id: str) -> bool:
        """Validate session exists and is not expired."""
        try:
            await self.get_session_state(session_id)
            return True
        except (SessionNotFoundError, SessionExpiredError):
            return False

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions and return count."""
        try:
            expired_sessions = await session_storage.list_expired_sessions()
            cleanup_count = 0

            for session_id in expired_sessions:
                try:
                    await session_storage.delete_session(session_id)
                    cleanup_count += 1
                except Exception as e:
                    logger.warning(
                        f"Failed to delete expired session {session_id}: {e}"
                    )

            if cleanup_count > 0:
                logger.info(f"Cleaned up {cleanup_count} expired sessions")

            return cleanup_count

        except Exception as e:
            logger.error(f"Session cleanup failed: {e}")
            return 0

    async def extend_session(self, session_id: str, hours: int = 1) -> SessionState:
        """Extend session expiration time."""
        session = await self.get_session_state(session_id)

        session.expires_at = datetime.utcnow() + timedelta(hours=hours)
        await session_storage.save_session(session)

        logger.info(
            "Session extended",
            extra={
                "session_id": session_id,
                "new_expires_at": session.expires_at.isoformat(),
            },
        )

        return session


# Global session manager instance
session_manager = SessionManager()
