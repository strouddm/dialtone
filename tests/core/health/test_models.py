"""Tests for health monitoring models."""

from datetime import datetime


from app.core.health.models import (
    HealthCheck,
    HealthResponse,
    HealthStatus,
    ServiceStatus,
    SystemMetrics,
)


def test_health_status_enum():
    """Test HealthStatus enum values."""
    assert HealthStatus.HEALTHY == "healthy"
    assert HealthStatus.DEGRADED == "degraded"
    assert HealthStatus.UNHEALTHY == "unhealthy"


def test_system_metrics_model():
    """Test SystemMetrics model validation."""
    metrics = SystemMetrics(
        cpu_percent=25.5,
        memory_percent=45.2,
        memory_used_gb=7.2,
        memory_total_gb=16.0,
        disk_percent=30.1,
        load_average=[1.2, 1.5, 1.8],
    )

    assert metrics.cpu_percent == 25.5
    assert metrics.memory_percent == 45.2
    assert metrics.memory_used_gb == 7.2
    assert metrics.memory_total_gb == 16.0
    assert metrics.disk_percent == 30.1
    assert metrics.load_average == [1.2, 1.5, 1.8]


def test_service_status_model():
    """Test ServiceStatus model."""
    service = ServiceStatus(
        name="fastapi", status=HealthStatus.HEALTHY, message="Service running normally"
    )

    assert service.name == "fastapi"
    assert service.status == HealthStatus.HEALTHY
    assert service.message == "Service running normally"


def test_health_check_model():
    """Test HealthCheck model."""
    check = HealthCheck(
        name="memory_usage",
        status=HealthStatus.HEALTHY,
        message="Memory usage within normal range",
    )

    assert check.name == "memory_usage"
    assert check.status == HealthStatus.HEALTHY
    assert check.message == "Memory usage within normal range"


def test_health_response_model():
    """Test complete HealthResponse model."""
    metrics = SystemMetrics(
        cpu_percent=25.5,
        memory_percent=45.2,
        memory_used_gb=7.2,
        memory_total_gb=16.0,
        disk_percent=30.1,
        load_average=[1.2, 1.5, 1.8],
    )

    checks = [
        HealthCheck(
            name="memory_usage",
            status=HealthStatus.HEALTHY,
            message="Memory usage normal",
        )
    ]

    services = {"fastapi": HealthStatus.HEALTHY}
    features = {"audio_upload": True, "transcription": False}

    response = HealthResponse(
        status=HealthStatus.HEALTHY,
        timestamp=datetime.utcnow(),
        version="1.0.0",
        uptime_seconds=3600.0,
        system=metrics,
        services=services,
        checks=checks,
        features=features,
        app_name="Dialtone",
    )

    assert response.status == HealthStatus.HEALTHY
    assert response.version == "1.0.0"
    assert response.uptime_seconds == 3600.0
    assert response.system == metrics
    assert response.services == services
    assert response.checks == checks
    assert response.features == features
    assert response.app_name == "Dialtone"


def test_health_response_serialization():
    """Test HealthResponse JSON serialization."""
    metrics = SystemMetrics(
        cpu_percent=25.5,
        memory_percent=45.2,
        memory_used_gb=7.2,
        memory_total_gb=16.0,
        disk_percent=30.1,
        load_average=[1.2, 1.5, 1.8],
    )

    response = HealthResponse(
        status=HealthStatus.HEALTHY,
        timestamp=datetime.utcnow(),
        version="1.0.0",
        uptime_seconds=3600.0,
        system=metrics,
        services={"fastapi": HealthStatus.HEALTHY},
        checks=[],
        features={"audio_upload": True},
        app_name="Dialtone",
    )

    # Should be able to serialize to dict
    data = response.model_dump()
    assert data["status"] == "healthy"
    assert data["version"] == "1.0.0"
    assert "system" in data
    assert "services" in data
