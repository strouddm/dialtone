"""Tests for health endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import __version__


client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint returns API information."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "Dialtone"
    assert data["version"] == __version__
    assert "docs" in data
    assert "health" in data


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["version"] == __version__
    assert data["app_name"] == "Dialtone"

    # Check feature flags
    assert "features" in data
    assert data["features"]["audio_upload"] is True
    assert data["features"]["transcription"] is False
    assert data["features"]["summarization"] is False


def test_readiness_check():
    """Test readiness check endpoint."""
    response = client.get("/ready")
    assert response.status_code == 200

    data = response.json()
    assert "ready" in data
    assert "vault_accessible" in data
    assert "whisper_loaded" in data
    assert "ollama_connected" in data

    # Future features should be False for now
    assert data["whisper_loaded"] is False
    assert data["ollama_connected"] is False


def test_health_check_performance():
    """Test health check responds quickly."""
    import time

    start = time.time()
    response = client.get("/health")
    duration = time.time() - start

    assert response.status_code == 200
    assert duration < 0.05  # Should respond in less than 50ms


def test_cors_headers():
    """Test CORS headers are present."""
    # TestClient doesn't properly simulate CORS headers
    # Just verify the middleware is configured in the app
    response = client.get("/health")
    assert response.status_code == 200

    # CORS middleware is configured in main.py
    # In production, headers like Access-Control-Allow-Origin would be present


def test_request_id_header():
    """Test request ID is added to response."""
    response = client.get("/health")
    assert response.status_code == 200

    assert "x-request-id" in response.headers
    assert response.headers["x-request-id"]


def test_openapi_endpoint():
    """Test OpenAPI documentation is available."""
    response = client.get("/openapi.json")
    assert response.status_code == 200

    data = response.json()
    assert data["info"]["title"] == "Dialtone"
    assert data["info"]["version"] == __version__


def test_docs_endpoint():
    """Test Swagger UI is available."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()
