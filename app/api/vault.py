"""Vault API endpoints."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.core.exceptions import VaultError
from app.models.common import SuccessResponse
from app.services.vault import vault_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vault", tags=["vault"])


class VaultSaveRequest(BaseModel):
    """Request model for saving to vault."""

    upload_id: str = Field(..., description="Upload identifier")
    transcription: str = Field(..., description="Transcription text")
    summary: Optional[str] = Field(None, description="AI-generated summary")
    keywords: Optional[List[str]] = Field(None, description="Extracted keywords")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, v):
        """Validate keywords list length."""
        if v is not None and len(v) > 10:
            raise ValueError("Too many keywords. Maximum 10 allowed.")
        return v


class VaultSaveResponse(SuccessResponse):
    """Response model for vault save operation."""

    file_path: str = Field(..., description="Relative path within vault")
    filename: str = Field(..., description="Generated filename")


@router.post(
    "/save",
    response_model=VaultSaveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save transcription to vault",
    description="Save formatted transcription with metadata to Obsidian vault",
    responses={
        201: {
            "description": "Successfully saved to vault",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Transcription saved to vault",
                        "file_path": "voice-note_2024-08-01_14-30_abc12345.md",
                        "filename": "voice-note_2024-08-01_14-30_abc12345.md",
                        "request_id": "req_123",
                    }
                }
            },
        },
        403: {
            "description": "Vault access denied",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unable to access vault",
                        "error_code": "VAULT_ACCESS_ERROR",
                        "request_id": "req_123",
                    }
                }
            },
        },
        500: {
            "description": "Failed to save to vault",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Failed to write file to vault",
                        "error_code": "VAULT_WRITE_ERROR",
                        "request_id": "req_123",
                    }
                }
            },
        },
    },
)
async def save_to_vault(request: VaultSaveRequest) -> VaultSaveResponse:
    """
    Save transcription to Obsidian vault.

    This endpoint formats the transcription using markdown with YAML frontmatter
    and saves it to the configured Obsidian vault directory.
    """
    try:
        result = await vault_service.save_transcription_to_vault(
            upload_id=request.upload_id,
            transcription=request.transcription,
            summary=request.summary,
            keywords=request.keywords,
            metadata=request.metadata,
        )

        logger.info(
            "Transcription saved to vault",
            extra={
                "upload_id": request.upload_id,
                "vault_filename": result["filename"],
            },
        )

        return VaultSaveResponse(
            success=True,
            message=f"Transcription saved to vault as {result['filename']}",
            file_path=result["file_path"],
            filename=result["filename"],
            request_id=None,
        )

    except VaultError:
        # Re-raise vault errors to be handled by error handlers
        raise
    except Exception as e:
        logger.error(f"Unexpected error saving to vault: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while saving to vault",
        )
