"""Background session cleanup tasks."""

import asyncio
import logging

from app.core.settings import settings
from app.services.session_manager import session_manager

logger = logging.getLogger(__name__)


async def cleanup_expired_sessions():
    """Background task to cleanup expired sessions."""
    while True:
        try:
            cleanup_count = await session_manager.cleanup_expired_sessions()

            if cleanup_count > 0:
                logger.info(f"Cleaned up {cleanup_count} expired sessions")

        except Exception as e:
            logger.error(f"Session cleanup task failed: {e}")

        # Wait for next cleanup cycle
        await asyncio.sleep(settings.session_cleanup_interval_minutes * 60)


def start_cleanup_task():
    """Start background cleanup task."""
    asyncio.create_task(cleanup_expired_sessions())
    logger.info(
        f"Session cleanup task started with {settings.session_cleanup_interval_minutes} minute intervals"
    )
