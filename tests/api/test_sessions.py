"""Tests for session API endpoints."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models.session import SessionState, SessionStatus


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def mock_session_manager():
    """Mock session manager."""
    with patch("app.api.sessions.session_manager") as mock:
        yield mock


@pytest.fixture
def mock_session_storage():
    """Mock session storage."""
    with patch("app.api.sessions.session_storage") as mock:
        yield mock


class TestSessionAPI:
    """Test session API endpoints."""

    def test_create_session_success(self, client, mock_session_manager):
        """Test successful session creation."""
        # Mock session manager - use AsyncMock for async methods
        test_session_id = "test_session_123"
        mock_session = SessionState(session_id=test_session_id)
        mock_session_manager.create_session = AsyncMock(return_value=test_session_id)
        mock_session_manager.get_session_state = AsyncMock(return_value=mock_session)

        response = client.post("/api/v1/sessions/")

        assert response.status_code == 201
        data = response.json()
        assert data["session_id"] == test_session_id
        assert data["status"] == "created"

    def test_get_session_success(self, client, mock_session_manager):
        """Test successful session retrieval."""
        session_id = "test_session_123"
        mock_session = SessionState(
            session_id=session_id,
            status=SessionStatus.PROCESSING,
        )
        mock_session_manager.get_session_state.return_value = mock_session

        response = client.get(f"/api/v1/sessions/{session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["status"] == "processing"

    def test_get_session_not_found(self, client, mock_session_manager):
        """Test getting non-existent session."""
        from app.services.session_manager import SessionNotFoundError

        session_id = "nonexistent_session"
        mock_session_manager.get_session_state.side_effect = SessionNotFoundError(
            f"Session {session_id} not found"
        )

        response = client.get(f"/api/v1/sessions/{session_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_session_expired(self, client, mock_session_manager):
        """Test getting expired session."""
        from app.services.session_manager import SessionExpiredError

        session_id = "expired_session"
        mock_session_manager.get_session_state.side_effect = SessionExpiredError(
            f"Session {session_id} has expired"
        )

        response = client.get(f"/api/v1/sessions/{session_id}")

        assert response.status_code == 410
        assert "expired" in response.json()["detail"].lower()

    def test_update_session_success(self, client, mock_session_manager):
        """Test successful session update."""
        session_id = "test_session_123"
        mock_session = SessionState(
            session_id=session_id,
            status=SessionStatus.EDITED,
            user_edits={"notes": "Test notes"},
        )
        mock_session_manager.update_session_data.return_value = mock_session

        update_data = {
            "status": "edited",
            "user_edits": {"notes": "Test notes"},
        }

        response = client.put(f"/api/v1/sessions/{session_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "edited"
        assert data["user_edits"] == {"notes": "Test notes"}

    def test_delete_session_success(self, client, mock_session_storage):
        """Test successful session deletion."""
        session_id = "test_session_123"
        mock_session_storage.delete_session.return_value = True

        response = client.delete(f"/api/v1/sessions/{session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted successfully" in data["message"]

    def test_delete_session_not_found(self, client, mock_session_storage):
        """Test deleting non-existent session."""
        session_id = "nonexistent_session"
        mock_session_storage.delete_session.return_value = False

        response = client.delete(f"/api/v1/sessions/{session_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_session_status_valid(self, client, mock_session_manager):
        """Test getting status of valid session."""
        session_id = "test_session_123"
        mock_session = SessionState(
            session_id=session_id,
            status=SessionStatus.TRANSCRIBED,
        )
        mock_session_manager.validate_session.return_value = True
        mock_session_manager.get_session_state.return_value = mock_session

        response = client.get(f"/api/v1/sessions/{session_id}/status")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["valid"] is True
        assert data["status"] == "transcribed"
        assert "expires_at" in data

    def test_get_session_status_invalid(self, client, mock_session_manager):
        """Test getting status of invalid session."""
        session_id = "invalid_session"
        mock_session_manager.validate_session.return_value = False

        response = client.get(f"/api/v1/sessions/{session_id}/status")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["valid"] is False
        assert data["status"] == "expired_or_missing"

    def test_update_session_partial_data(self, client, mock_session_manager):
        """Test updating session with partial data."""
        session_id = "test_session_123"
        mock_session = SessionState(
            session_id=session_id,
            status=SessionStatus.PROCESSING,
        )
        mock_session_manager.update_session_data.return_value = mock_session

        # Only update status
        update_data = {"status": "processing"}

        response = client.put(f"/api/v1/sessions/{session_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"

    def test_create_session_empty_request(self, client, mock_session_manager):
        """Test creating session with empty request body."""
        test_session_id = "test_session_123"
        mock_session = SessionState(session_id=test_session_id)
        mock_session_manager.create_session.return_value = test_session_id
        mock_session_manager.get_session_state.return_value = mock_session

        # Send empty JSON
        response = client.post("/api/v1/sessions/", json={})

        assert response.status_code == 201
        data = response.json()
        assert data["session_id"] == test_session_id

    def test_session_api_error_handling(self, client, mock_session_manager):
        """Test API error handling for session operations."""
        session_id = "test_session_123"

        # Mock storage error
        mock_session_manager.get_session_state.side_effect = Exception("Storage error")

        response = client.get(f"/api/v1/sessions/{session_id}")

        # Should be handled by global exception handler
        assert response.status_code >= 400
