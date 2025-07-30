"""Health monitoring data models."""

from datetime import datetime
from enum import Enum
from typing import Dict, List

from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    """Health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class SystemMetrics(BaseModel):
    """System resource metrics."""

    cpu_percent: float = Field(..., description="CPU usage percentage")
    memory_percent: float = Field(..., description="Memory usage percentage")
    memory_used_gb: float = Field(..., description="Memory used in GB")
    memory_total_gb: float = Field(..., description="Total memory in GB")
    disk_percent: float = Field(..., description="Disk usage percentage")
    load_average: List[float] = Field(
        ..., description="System load average (1, 5, 15 min)"
    )


class ServiceStatus(BaseModel):
    """Service dependency status."""

    name: str
    status: HealthStatus
    message: str


class HealthCheck(BaseModel):
    """Individual health check result."""

    name: str
    status: HealthStatus
    message: str


class HealthResponse(BaseModel):
    """Complete health response model."""

    status: HealthStatus
    timestamp: datetime
    version: str
    uptime_seconds: float
    system: SystemMetrics
    services: Dict[str, HealthStatus]
    checks: List[HealthCheck]
    # Backward compatibility
    features: Dict[str, bool]
    app_name: str
