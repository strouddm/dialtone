"""Session storage service using file-based JSON storage."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import aiofiles

from app.core.exceptions import ServiceError
from app.core.settings import settings
from app.models.session import SessionState


class SessionStorageError(ServiceError):
    """Session storage related errors."""

    pass


class SessionStorage:
    """File-based session storage with async operations."""

    def __init__(self):
        self.storage_dir = settings.session_storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._locks: Dict[str, asyncio.Lock] = {}

    def _get_session_path(self, session_id: str) -> Path:
        """Get file path for session."""
        return Path(self.storage_dir / f"{session_id}.json")

    async def _get_lock(self, session_id: str) -> asyncio.Lock:
        """Get or create lock for session."""
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    async def create_session(self) -> SessionState:
        """Create new session with unique ID."""
        session = SessionState()
        await self.save_session(session)
        return session

    async def get_session(self, session_id: str) -> Optional[SessionState]:
        """Retrieve session by ID."""
        session_path = self._get_session_path(session_id)

        if not session_path.exists():
            return None

        try:
            async with aiofiles.open(session_path, "r") as f:
                data = await f.read()
                session_data = json.loads(data)
                return SessionState(**session_data)
        except Exception as e:
            raise SessionStorageError(f"Failed to load session {session_id}: {e}")

    async def save_session(self, session: SessionState) -> None:
        """Save session to storage."""
        session.updated_at = datetime.utcnow()
        session_path = self._get_session_path(session.session_id)

        lock = await self._get_lock(session.session_id)
        async with lock:
            try:
                async with aiofiles.open(session_path, "w") as f:
                    data = session.model_dump_json(indent=2)
                    await f.write(data)
            except Exception as e:
                raise SessionStorageError(
                    f"Failed to save session {session.session_id}: {e}"
                )

    async def delete_session(self, session_id: str) -> bool:
        """Delete session from storage."""
        session_path = self._get_session_path(session_id)

        if not session_path.exists():
            return False

        try:
            session_path.unlink()
            # Clean up lock
            self._locks.pop(session_id, None)
            return True
        except Exception as e:
            raise SessionStorageError(f"Failed to delete session {session_id}: {e}")

    async def list_expired_sessions(self) -> List[str]:
        """Get list of expired session IDs."""
        expired_sessions = []
        current_time = datetime.utcnow()

        for session_file in self.storage_dir.glob("*.json"):
            try:
                async with aiofiles.open(session_file, "r") as f:
                    data = await f.read()
                    session_data = json.loads(data)
                    expires_at = datetime.fromisoformat(session_data["expires_at"])

                    if expires_at < current_time:
                        expired_sessions.append(session_data["session_id"])
            except Exception:
                # Skip corrupted files
                continue

        return expired_sessions


# Global storage instance
session_storage = SessionStorage()
