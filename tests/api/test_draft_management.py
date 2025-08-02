"""Tests for draft management endpoints."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

from app.models.session import DraftData, SessionStatus
from app.services.session_manager import SessionExpiredError, SessionNotFoundError


class TestDraftManagement:
    """Test suite for draft management functionality."""

    @pytest.fixture
    async def session_with_data(self, test_client: AsyncClient):
        """Create a session with transcription data for testing."""
        # Create session
        response = await test_client.post("/api/v1/sessions/")
        assert response.status_code == status.HTTP_201_CREATED
        session_data = response.json()
        session_id = session_data["session_id"]

        # Mock session with transcription data
        mock_session_state = {
            "session_id": session_id,
            "status": SessionStatus.TRANSCRIBED,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "expires_at": datetime.utcnow(),
            "transcription": {
                "text": "This is a test transcription",
                "language": "en",
                "confidence": 0.95,
                "processing_time_seconds": 2.5,
            },
            "summary": "This is a test summary",
            "keywords": ["test", "transcription"],
            "draft": None,
        }

        return session_id, mock_session_state

    async def test_update_draft_success(
        self, test_client: AsyncClient, session_with_data
    ):
        """Test successful draft update."""
        session_id, mock_session_state = session_with_data

        draft_data = {
            "transcription": "Updated transcription text",
            "summary": ["Updated summary point 1", "Updated summary point 2"],
            "keywords": ["updated", "keywords"],
        }

        with patch(
            "app.services.session_manager.session_manager.update_session_data"
        ) as mock_update:
            # Mock updated session state with draft
            updated_state = mock_session_state.copy()
            updated_state["draft"] = DraftData(**draft_data)
            mock_update.return_value = type("MockSession", (), updated_state)()

            response = await test_client.patch(
                f"/api/v1/sessions/{session_id}/draft", json=draft_data
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["session_id"] == session_id
            assert data["draft"]["transcription"] == draft_data["transcription"]
            assert data["draft"]["summary"] == draft_data["summary"]
            assert data["draft"]["keywords"] == draft_data["keywords"]

            mock_update.assert_called_once()

    async def test_update_draft_partial_data(
        self, test_client: AsyncClient, session_with_data
    ):
        """Test draft update with partial data."""
        session_id, mock_session_state = session_with_data

        # Only update transcription
        draft_data = {"transcription": "Only transcription updated"}

        with patch(
            "app.services.session_manager.session_manager.update_session_data"
        ) as mock_update:
            updated_state = mock_session_state.copy()
            updated_state["draft"] = DraftData(
                transcription=draft_data["transcription"]
            )
            mock_update.return_value = type("MockSession", (), updated_state)()

            response = await test_client.patch(
                f"/api/v1/sessions/{session_id}/draft", json=draft_data
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["draft"]["transcription"] == draft_data["transcription"]
            assert data["draft"]["summary"] is None
            assert data["draft"]["keywords"] is None

    async def test_update_draft_session_not_found(self, test_client: AsyncClient):
        """Test draft update with non-existent session."""
        draft_data = {"transcription": "Test transcription"}

        with patch(
            "app.services.session_manager.session_manager.update_session_data"
        ) as mock_update:
            mock_update.side_effect = SessionNotFoundError("Session not found")

            response = await test_client.patch(
                "/api/v1/sessions/nonexistent/draft", json=draft_data
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_update_draft_session_expired(self, test_client: AsyncClient):
        """Test draft update with expired session."""
        draft_data = {"transcription": "Test transcription"}

        with patch(
            "app.services.session_manager.session_manager.update_session_data"
        ) as mock_update:
            mock_update.side_effect = SessionExpiredError("Session expired")

            response = await test_client.patch(
                "/api/v1/sessions/expired-session/draft", json=draft_data
            )

            assert response.status_code == status.HTTP_410_GONE

    async def test_preview_markdown_success(
        self, test_client: AsyncClient, session_with_data
    ):
        """Test successful markdown preview generation."""
        session_id, mock_session_state = session_with_data

        with patch(
            "app.services.session_manager.session_manager.get_session_state"
        ) as mock_get_session:
            with patch(
                "app.services.markdown_formatter.markdown_formatter.format_note"
            ) as mock_format:
                mock_get_session.return_value = type(
                    "MockSession", (), mock_session_state
                )()
                mock_format.return_value = "# Test Note\n\nThis is a test note."

                response = await test_client.get(
                    f"/api/v1/sessions/{session_id}/preview"
                )

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["session_id"] == session_id
                assert "markdown" in data
                assert "character_count" in data
                assert "word_count" in data
                assert data["markdown"] == "# Test Note\n\nThis is a test note."

                # Verify markdown formatter was called with original data
                mock_format.assert_called_once()
                call_args = mock_format.call_args
                assert call_args[1]["transcription"] == "This is a test transcription"
                assert call_args[1]["summary"] == ["This is a test summary"]
                assert call_args[1]["keywords"] == ["test", "transcription"]

    async def test_preview_markdown_with_draft(
        self, test_client: AsyncClient, session_with_data
    ):
        """Test markdown preview with draft data taking precedence."""
        session_id, mock_session_state = session_with_data

        # Add draft data to session
        draft_data = DraftData(
            transcription="Draft transcription",
            summary=["Draft summary point 1", "Draft summary point 2"],
            keywords=["draft", "keywords"],
        )
        mock_session_state["draft"] = draft_data

        with patch(
            "app.services.session_manager.session_manager.get_session_state"
        ) as mock_get_session:
            with patch(
                "app.services.markdown_formatter.markdown_formatter.format_note"
            ) as mock_format:
                mock_get_session.return_value = type(
                    "MockSession", (), mock_session_state
                )()
                mock_format.return_value = "# Draft Note\n\nThis is a draft note."

                response = await test_client.get(
                    f"/api/v1/sessions/{session_id}/preview"
                )

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["markdown"] == "# Draft Note\n\nThis is a draft note."

                # Verify markdown formatter was called with draft data
                mock_format.assert_called_once()
                call_args = mock_format.call_args
                assert call_args[1]["transcription"] == "Draft transcription"
                assert call_args[1]["summary"] == [
                    "Draft summary point 1",
                    "Draft summary point 2",
                ]
                assert call_args[1]["keywords"] == ["draft", "keywords"]

    async def test_preview_markdown_empty_session(self, test_client: AsyncClient):
        """Test markdown preview with session containing no transcription."""
        session_id = "test-session"

        mock_session_state = {
            "session_id": session_id,
            "status": SessionStatus.CREATED,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "expires_at": datetime.utcnow(),
            "transcription": None,
            "summary": None,
            "keywords": None,
            "draft": None,
        }

        with patch(
            "app.services.session_manager.session_manager.get_session_state"
        ) as mock_get_session:
            with patch(
                "app.services.markdown_formatter.markdown_formatter.format_note"
            ) as mock_format:
                mock_get_session.return_value = type(
                    "MockSession", (), mock_session_state
                )()
                mock_format.return_value = "# Empty Note\n\nNo content available."

                response = await test_client.get(
                    f"/api/v1/sessions/{session_id}/preview"
                )

                assert response.status_code == status.HTTP_200_OK
                data = response.json()

                # Verify markdown formatter was called with empty data
                mock_format.assert_called_once()
                call_args = mock_format.call_args
                assert call_args[1]["transcription"] == ""
                assert call_args[1]["summary"] == []
                assert call_args[1]["keywords"] == []

    async def test_preview_markdown_session_not_found(self, test_client: AsyncClient):
        """Test markdown preview with non-existent session."""
        with patch(
            "app.services.session_manager.session_manager.get_session_state"
        ) as mock_get_session:
            mock_get_session.side_effect = SessionNotFoundError("Session not found")

            response = await test_client.get("/api/v1/sessions/nonexistent/preview")

            assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_preview_markdown_session_expired(self, test_client: AsyncClient):
        """Test markdown preview with expired session."""
        with patch(
            "app.services.session_manager.session_manager.get_session_state"
        ) as mock_get_session:
            mock_get_session.side_effect = SessionExpiredError("Session expired")

            response = await test_client.get("/api/v1/sessions/expired-session/preview")

            assert response.status_code == status.HTTP_410_GONE

    async def test_draft_data_validation(
        self, test_client: AsyncClient, session_with_data
    ):
        """Test draft data validation."""
        session_id, _ = session_with_data

        # Test with invalid data types
        invalid_draft_data = {
            "transcription": 123,  # Should be string
            "summary": "not a list",  # Should be list
            "keywords": {"not": "a list"},  # Should be list
        }

        response = await test_client.patch(
            f"/api/v1/sessions/{session_id}/draft", json=invalid_draft_data
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_draft_character_limits(
        self, test_client: AsyncClient, session_with_data
    ):
        """Test draft data with large content."""
        session_id, mock_session_state = session_with_data

        # Test with very long transcription
        long_transcription = "A" * 50000  # 50k characters
        draft_data = {
            "transcription": long_transcription,
            "summary": ["Test summary"],
            "keywords": ["test"],
        }

        with patch(
            "app.services.session_manager.session_manager.update_session_data"
        ) as mock_update:
            updated_state = mock_session_state.copy()
            updated_state["draft"] = DraftData(**draft_data)
            mock_update.return_value = type("MockSession", (), updated_state)()

            response = await test_client.patch(
                f"/api/v1/sessions/{session_id}/draft", json=draft_data
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data["draft"]["transcription"]) == 50000

    async def test_empty_draft_update(
        self, test_client: AsyncClient, session_with_data
    ):
        """Test updating draft with empty data."""
        session_id, mock_session_state = session_with_data

        draft_data = {}  # Empty draft update

        with patch(
            "app.services.session_manager.session_manager.update_session_data"
        ) as mock_update:
            updated_state = mock_session_state.copy()
            updated_state["draft"] = DraftData()
            mock_update.return_value = type("MockSession", (), updated_state)()

            response = await test_client.patch(
                f"/api/v1/sessions/{session_id}/draft", json=draft_data
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["draft"]["transcription"] is None
            assert data["draft"]["summary"] is None
            assert data["draft"]["keywords"] is None

    @pytest.mark.asyncio
    async def test_concurrent_draft_updates(
        self, test_client: AsyncClient, session_with_data
    ):
        """Test handling of concurrent draft updates."""
        session_id, mock_session_state = session_with_data

        draft_data_1 = {"transcription": "First update"}
        draft_data_2 = {"transcription": "Second update"}

        with patch(
            "app.services.session_manager.session_manager.update_session_data"
        ) as mock_update:
            updated_state = mock_session_state.copy()

            # First update
            updated_state["draft"] = DraftData(**draft_data_1)
            mock_update.return_value = type("MockSession", (), updated_state)()

            response1 = await test_client.patch(
                f"/api/v1/sessions/{session_id}/draft", json=draft_data_1
            )

            # Second update
            updated_state["draft"] = DraftData(**draft_data_2)
            mock_update.return_value = type("MockSession", (), updated_state)()

            response2 = await test_client.patch(
                f"/api/v1/sessions/{session_id}/draft", json=draft_data_2
            )

            assert response1.status_code == status.HTTP_200_OK
            assert response2.status_code == status.HTTP_200_OK

            # Last update should win
            data2 = response2.json()
            assert data2["draft"]["transcription"] == "Second update"
