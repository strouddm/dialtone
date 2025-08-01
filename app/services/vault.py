"""Service for saving transcriptions to Obsidian vault."""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiofiles
import aiofiles.os

from app.core.exceptions import (
    VaultAccessError,
    VaultConfigurationError,
    VaultWriteError,
)
from app.core.settings import settings
from app.services.markdown_formatter import markdown_formatter

logger = logging.getLogger(__name__)


class VaultService:
    """Service for managing Obsidian vault operations."""

    def __init__(self):
        """Initialize vault service."""
        self.vault_path = settings.obsidian_vault_path
        self._validate_configuration()

    def _validate_configuration(self) -> None:
        """Validate vault configuration at initialization."""
        if not self.vault_path:
            raise VaultConfigurationError(
                "Vault path not configured",
                details={"config_key": "OBSIDIAN_VAULT_PATH"},
            )

    async def save_transcription_to_vault(
        self,
        upload_id: str,
        transcription: str,
        summary: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Save formatted transcription to Obsidian vault.

        Args:
            upload_id: Unique upload identifier
            transcription: Raw transcription text
            summary: Optional AI-generated summary
            keywords: Optional extracted keywords
            metadata: Optional additional metadata

        Returns:
            Dict containing success status, file path, and filename

        Raises:
            VaultAccessError: If vault is not accessible
            VaultWriteError: If file writing fails
        """
        # Validate vault access
        await self._validate_vault_access()

        # Format content using existing formatter
        content = markdown_formatter.format_transcription(
            transcription_text=transcription,
            summary=summary,
            keywords=keywords,
            metadata=metadata,
            upload_id=upload_id,
        )

        # Generate filename
        filename = self._generate_filename(upload_id)

        # Handle potential duplicates
        final_path = await self._handle_duplicate_filename(filename)

        # Write file atomically
        await self._atomic_write(final_path, content)

        # Prepare response
        relative_path = final_path.relative_to(self.vault_path)

        logger.info(
            "Successfully saved transcription to vault",
            extra={
                "upload_id": upload_id,
                "vault_filename": final_path.name,
                "vault_path": str(relative_path),
                "content_size": len(content),
            },
        )

        return {
            "success": True,
            "file_path": str(relative_path),
            "filename": final_path.name,
            "full_path": str(final_path),
        }

    async def _validate_vault_access(self) -> None:
        """
        Validate vault directory exists and is writable.

        Raises:
            VaultAccessError: If vault is not accessible
        """
        try:
            # Check if path exists
            if not await aiofiles.os.path.exists(str(self.vault_path)):
                # Try to create directory
                await aiofiles.os.makedirs(str(self.vault_path), exist_ok=True)
                logger.info(f"Created vault directory: {self.vault_path}")

            # Check if it's a directory
            if not await aiofiles.os.path.isdir(str(self.vault_path)):
                raise VaultAccessError(
                    "Vault path is not a directory",
                    details={"vault_path": str(self.vault_path)},
                )

            # Check write permissions by creating a test file
            test_file = self.vault_path / ".dialtone_write_test"
            try:
                async with aiofiles.open(str(test_file), "w") as f:
                    await f.write("test")
                await aiofiles.os.remove(str(test_file))
            except Exception as e:
                raise VaultAccessError(
                    "No write permission for vault directory",
                    details={
                        "vault_path": str(self.vault_path),
                        "error": str(e),
                    },
                )

        except VaultAccessError:
            raise
        except Exception as e:
            logger.error(f"Vault access validation failed: {e}")
            raise VaultAccessError(
                "Failed to validate vault access",
                details={"vault_path": str(self.vault_path), "error": str(e)},
            )

    def _generate_filename(self, upload_id: str) -> str:
        """
        Generate a safe filename for the note.

        Args:
            upload_id: Upload identifier

        Returns:
            Generated filename with .md extension
        """
        timestamp = datetime.now()
        return (
            markdown_formatter.format_for_obsidian_filename(upload_id, timestamp)
            + ".md"
        )

    async def _handle_duplicate_filename(self, base_filename: str) -> Path:
        """
        Handle duplicate filenames by appending numbers.

        Args:
            base_filename: Original filename

        Returns:
            Path object with unique filename
        """
        base_path = self.vault_path / base_filename

        # If no conflict, return original
        if not await aiofiles.os.path.exists(str(base_path)):
            return Path(str(base_path))

        # Find unique filename with suffix
        name_parts = base_filename.rsplit(".", 1)
        base_name = name_parts[0]
        extension = f".{name_parts[1]}" if len(name_parts) > 1 else ""

        counter = 1
        while counter < 1000:  # Prevent infinite loop
            new_filename = f"{base_name}_{counter:03d}{extension}"
            new_path = self.vault_path / new_filename

            if not await aiofiles.os.path.exists(str(new_path)):
                logger.debug(
                    f"Resolved filename conflict: {base_filename} -> {new_filename}"
                )
                return Path(str(new_path))

            counter += 1

        # This should rarely happen
        raise VaultWriteError(
            "Unable to generate unique filename",
            details={"base_filename": base_filename, "attempts": counter},
        )

    async def _atomic_write(self, file_path: Path, content: str) -> None:
        """
        Write file atomically to prevent corruption.

        Args:
            file_path: Target file path
            content: File content to write

        Raises:
            VaultWriteError: If write operation fails
        """
        temp_path = file_path.with_suffix(f"{file_path.suffix}.tmp")

        try:
            # Write to temporary file
            async with aiofiles.open(str(temp_path), "w", encoding="utf-8") as f:
                await f.write(content)
                await f.flush()
                await asyncio.get_event_loop().run_in_executor(
                    None, os.fsync, f.fileno()
                )

            # Atomic rename
            await aiofiles.os.rename(str(temp_path), str(file_path))

        except Exception as e:
            # Clean up temp file if it exists
            try:
                if await aiofiles.os.path.exists(str(temp_path)):
                    await aiofiles.os.remove(str(temp_path))
            except Exception:
                pass

            logger.error(f"Failed to write file: {e}", exc_info=True)
            raise VaultWriteError(
                "Failed to save file to vault",
                details={
                    "file_path": str(file_path),
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

    async def get_vault_status(self) -> Dict[str, Any]:
        """
        Get vault status for health checks.

        Returns:
            Dict with vault status information
        """
        try:
            await self._validate_vault_access()

            # Get disk usage info
            stat = await asyncio.get_event_loop().run_in_executor(
                None, os.statvfs, str(self.vault_path)
            )
            free_space_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
            total_space_gb = (stat.f_blocks * stat.f_frsize) / (1024**3)

            return {
                "accessible": True,
                "path": str(self.vault_path),
                "free_space_gb": round(free_space_gb, 2),
                "total_space_gb": round(total_space_gb, 2),
                "writable": True,
            }
        except Exception as e:
            logger.error(f"Failed to get vault status: {e}")
            return {
                "accessible": False,
                "path": str(self.vault_path),
                "error": str(e),
                "writable": False,
            }


# Global service instance
vault_service = VaultService()
