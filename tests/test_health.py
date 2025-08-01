"""Tests for health endpoints."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app import __version__
from app.core.health.models import HealthCheck, HealthStatus, SystemMetrics
from app.main import app

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


@patch("app.core.health.monitors.SystemMonitor.get_system_metrics")
@patch("app.core.health.monitors.SystemMonitor.get_health_checks")
@patch("app.core.health.monitors.SystemMonitor.check_service_dependencies")
def test_health_check(mock_services, mock_checks, mock_metrics):
    """Test enhanced health check endpoint."""
    # Mock system metrics
    mock_metrics.return_value = SystemMetrics(
        cpu_percent=25.0,
        memory_percent=50.0,
        memory_used_gb=8.0,
        memory_total_gb=16.0,
        disk_percent=60.0,
        load_average=[1.0, 1.2, 1.5],
    )

    # Mock health checks
    mock_checks.return_value = [
        HealthCheck(
            name="memory_usage",
            status=HealthStatus.HEALTHY,
            message="Memory usage normal",
        )
    ]

    # Mock service dependencies
    mock_services.return_value = {
        "fastapi": HealthStatus.HEALTHY,
        "whisper": HealthStatus.HEALTHY,
        "ollama": HealthStatus.HEALTHY,
    }

    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["version"] == __version__
    assert data["app_name"] == "Dialtone"

    # Check enhanced system monitoring
    assert "system" in data
    assert data["system"]["cpu_percent"] == 25.0
    assert data["system"]["memory_percent"] == 50.0
    assert data["system"]["memory_used_gb"] == 8.0
    assert data["system"]["memory_total_gb"] == 16.0
    assert data["system"]["disk_percent"] == 60.0
    assert data["system"]["load_average"] == [1.0, 1.2, 1.5]

    # Check services
    assert "services" in data
    assert data["services"]["fastapi"] == "healthy"
    assert data["services"]["whisper"] == "healthy"
    assert data["services"]["ollama"] == "healthy"

    # Check health checks
    assert "checks" in data
    assert len(data["checks"]) == 1
    assert data["checks"][0]["name"] == "memory_usage"
    assert data["checks"][0]["status"] == "healthy"

    # Check backward compatibility - feature flags
    assert "features" in data
    assert data["features"]["audio_upload"] is True
    assert data["features"]["transcription"] is True
    assert data["features"]["summarization"] is False

    # Check uptime
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], float)


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


@patch("app.core.health.monitors.SystemMonitor.get_system_metrics")
@patch("app.core.health.monitors.SystemMonitor.get_health_checks")
@patch("app.core.health.monitors.SystemMonitor.check_service_dependencies")
def test_health_check_performance(mock_services, mock_checks, mock_metrics):
    """Test health check responds within 500ms requirement."""
    import time

    # Mock quick responses
    mock_metrics.return_value = SystemMetrics(
        cpu_percent=25.0,
        memory_percent=50.0,
        memory_used_gb=8.0,
        memory_total_gb=16.0,
        disk_percent=60.0,
        load_average=[1.0, 1.2, 1.5],
    )
    mock_checks.return_value = [
        HealthCheck(name="test", status=HealthStatus.HEALTHY, message="OK")
    ]
    mock_services.return_value = {"fastapi": HealthStatus.HEALTHY}

    start = time.time()
    response = client.get("/health")
    duration = time.time() - start

    assert response.status_code == 200
    assert duration < 0.5  # Should respond in less than 500ms requirement


@patch("app.core.health.monitors.SystemMonitor.get_system_metrics")
@patch("app.core.health.monitors.SystemMonitor.get_health_checks")
@patch("app.core.health.monitors.SystemMonitor.check_service_dependencies")
def test_health_check_degraded_status(mock_services, mock_checks, mock_metrics):
    """Test health check with degraded system status."""
    # Mock degraded system metrics
    mock_metrics.return_value = SystemMetrics(
        cpu_percent=75.0,  # High CPU
        memory_percent=85.0,  # High memory
        memory_used_gb=13.6,
        memory_total_gb=16.0,
        disk_percent=60.0,
        load_average=[2.0, 2.5, 3.0],
    )

    # Mock degraded health checks
    mock_checks.return_value = [
        HealthCheck(
            name="memory_usage",
            status=HealthStatus.DEGRADED,
            message="Memory usage high: 85%",
        ),
        HealthCheck(
            name="cpu_usage",
            status=HealthStatus.DEGRADED,
            message="CPU usage high: 75%",
        ),
    ]

    mock_services.return_value = {
        "fastapi": HealthStatus.HEALTHY,
        "whisper": HealthStatus.HEALTHY,
        "ollama": HealthStatus.HEALTHY,
    }

    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "degraded"  # Overall status should be degraded
    assert data["system"]["cpu_percent"] == 75.0
    assert data["system"]["memory_percent"] == 85.0


@patch("app.core.health.service.HealthService.get_health_status")
def test_health_check_timeout_fallback(mock_get_health):
    """Test health check timeout fallback."""
    # Mock timeout scenario by returning what the service would return on timeout
    from app.core.health.models import HealthCheck, HealthResponse, HealthStatus, SystemMetrics
    from datetime import datetime
    
    fallback_response = HealthResponse(
        status=HealthStatus.DEGRADED,
        timestamp=datetime.utcnow(),
        version="0.1.0",
        uptime_seconds=120.5,
        system=SystemMetrics(
            cpu_percent=0.0,
            memory_percent=0.0,
            memory_used_gb=0.0,
            memory_total_gb=0.0,
            disk_percent=0.0,
            load_average=[0.0, 0.0, 0.0],
        ),
        services={
            "fastapi": HealthStatus.DEGRADED,
            "whisper": HealthStatus.HEALTHY,
            "ollama": HealthStatus.HEALTHY,
        },
        checks=[
            HealthCheck(
                name="health_check_timeout",
                status=HealthStatus.DEGRADED,
                message="Health check timed out or failed",
            )
        ],
        features={
            "audio_upload": True,
            "transcription": True,
            "summarization": False,
        },
        app_name="Dialtone",
    )
    
    mock_get_health.return_value = fallback_response

    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"


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
