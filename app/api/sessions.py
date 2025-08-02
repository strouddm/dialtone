"""Session management API endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.models.common import SuccessResponse
from app.models.session import (
    DraftData,
    SessionCreateRequest,
    SessionResponse,
    SessionUpdateRequest,
)
from app.services.session_manager import (
    SessionExpiredError,
    SessionNotFoundError,
    session_manager,
)
from app.services.session_storage import session_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post(
    "/",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new session",
    description="Create a new session for multi-step voice processing workflow",
)
async def create_session(
    request: Request, session_request: SessionCreateRequest = SessionCreateRequest()
) -> SessionResponse:
    """Create new session for voice processing workflow."""
    request_id = getattr(request.state, "request_id", "unknown")

    logger.info("Session creation requested", extra={"request_id": request_id})

    session_id = await session_manager.create_session()
    session_state = await session_manager.get_session_state(session_id)

    return SessionResponse(**session_state.model_dump())


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get session state",
    description="Retrieve current state of session",
)
async def get_session(request: Request, session_id: str) -> SessionResponse:
    """Get session state by ID."""
    request_id = getattr(request.state, "request_id", "unknown")

    logger.info(
        "Session state requested",
        extra={"request_id": request_id, "session_id": session_id},
    )

    try:
        session_state = await session_manager.get_session_state(session_id)
        return SessionResponse(**session_state.model_dump())
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e))


@router.put(
    "/{session_id}",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Update session",
    description="Update session with new data",
)
async def update_session(
    request: Request, session_id: str, update_request: SessionUpdateRequest
) -> SessionResponse:
    """Update session with new data."""
    request_id = getattr(request.state, "request_id", "unknown")

    logger.info(
        "Session update requested",
        extra={"request_id": request_id, "session_id": session_id},
    )

    try:
        update_data = update_request.model_dump(exclude_unset=True)
        session_state = await session_manager.update_session_data(
            session_id, **update_data
        )
        return SessionResponse(**session_state.model_dump())
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e))


@router.delete(
    "/{session_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete session",
    description="Delete session and cleanup associated data",
)
async def delete_session(request: Request, session_id: str) -> SuccessResponse:
    """Delete session and cleanup data."""
    request_id = getattr(request.state, "request_id", "unknown")

    logger.info(
        "Session deletion requested",
        extra={"request_id": request_id, "session_id": session_id},
    )

    success = await session_storage.delete_session(session_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return SuccessResponse(
        success=True,
        message=f"Session {session_id} deleted successfully",
        request_id=request_id,
    )


@router.get(
    "/{session_id}/status",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Check session status",
    description="Quick session status check",
)
async def get_session_status(request: Request, session_id: str) -> dict:
    """Get session status quickly."""
    is_valid = await session_manager.validate_session(session_id)

    if not is_valid:
        return {
            "session_id": session_id,
            "valid": False,
            "status": "expired_or_missing",
        }

    session_state = await session_manager.get_session_state(session_id)
    return {
        "session_id": session_id,
        "valid": True,
        "status": session_state.status,
        "expires_at": session_state.expires_at.isoformat(),
    }


@router.patch(
    "/{session_id}/draft",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Update session draft",
    description="Update draft data for editing session",
)
async def update_draft(
    request: Request, session_id: str, draft: DraftData
) -> SessionResponse:
    """Update session draft data."""
    request_id = getattr(request.state, "request_id", "unknown")

    logger.info(
        "Draft update requested",
        extra={"request_id": request_id, "session_id": session_id},
    )

    try:
        session_state = await session_manager.update_session_data(
            session_id, draft=draft
        )
        return SessionResponse(**session_state.model_dump())
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e))


@router.get(
    "/{session_id}/preview",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Preview session markdown",
    description="Generate markdown preview from current session data",
)
async def preview_markdown(request: Request, session_id: str) -> dict:
    """Generate markdown preview from session data."""
    request_id = getattr(request.state, "request_id", "unknown")

    logger.info(
        "Markdown preview requested",
        extra={"request_id": request_id, "session_id": session_id},
    )

    try:
        from app.services.markdown_formatter import markdown_formatter

        session_state = await session_manager.get_session_state(session_id)

        # Use draft data if available, otherwise use original data
        transcription_text = (
            session_state.draft.transcription
            if session_state.draft and session_state.draft.transcription
            else session_state.transcription.text if session_state.transcription else ""
        )

        summary_data = (
            session_state.draft.summary
            if session_state.draft and session_state.draft.summary
            else session_state.summary.split("\n") if session_state.summary else []
        )

        keywords_data = (
            session_state.draft.keywords
            if session_state.draft and session_state.draft.keywords
            else session_state.keywords or []
        )

        markdown_content = markdown_formatter.format_transcription(
            transcription_text=transcription_text,
            summary="\n".join(summary_data) if summary_data else None,
            keywords=keywords_data,
            metadata={
                "created_at": session_state.created_at.isoformat(),
                "session_id": session_id,
            },
        )

        return {
            "session_id": session_id,
            "markdown": markdown_content,
            "character_count": len(markdown_content),
            "word_count": len(markdown_content.split()),
        }
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SessionExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e))
