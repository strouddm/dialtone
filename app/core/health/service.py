"""Health service orchestrator."""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List

from app import __version__
from app.core.settings import settings

from .models import HealthCheck, HealthResponse, HealthStatus, SystemMetrics
from .monitors import SystemMonitor

logger = logging.getLogger(__name__)

# Application start time for uptime calculation
_start_time = time.time()


class HealthService:
    """Health service orchestrator coordinating all health checks."""

    def __init__(self):
        self.monitor = SystemMonitor()

    async def get_health_status(self) -> HealthResponse:
        """Get comprehensive health status with timeout protection."""
        try:
            # Use timeout to ensure response within 500ms requirement
            return await asyncio.wait_for(
                self._perform_health_checks(),
                timeout=0.4,  # 400ms timeout to stay under 500ms requirement
            )
        except asyncio.TimeoutError:
            logger.warning("Health check timed out, returning degraded status")
            return await self._get_fallback_health_status()
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return await self._get_fallback_health_status()

    async def _perform_health_checks(self) -> HealthResponse:
        """Perform all health checks and compile response."""
        # Get system metrics
        system_metrics = await self.monitor.get_system_metrics()

        # Get health checks based on metrics
        health_checks = await self.monitor.get_health_checks(system_metrics)

        # Check service dependencies
        services = await self.monitor.check_service_dependencies()

        # Determine overall status
        overall_status = self._determine_overall_status(health_checks, services)

        # Calculate uptime
        uptime_seconds = time.time() - _start_time

        return HealthResponse(
            status=overall_status,
            timestamp=datetime.utcnow(),
            version=__version__,
            uptime_seconds=round(uptime_seconds, 2),
            system=system_metrics,
            services=services,
            checks=health_checks,
            # Backward compatibility
            features={
                "audio_upload": True,  # Completed in issue #2
                "transcription": True,  # Completed in issue #3
                "vault_integration": True,  # Completed in issue #12
                "summarization": False,  # Will be True after issue #9
            },
            app_name=settings.app_name,
        )

    async def _get_fallback_health_status(self) -> HealthResponse:
        """Get basic health status when full checks fail."""
        uptime_seconds = time.time() - _start_time

        # Basic system metrics fallback
        fallback_metrics = SystemMetrics(
            cpu_percent=0.0,
            memory_percent=0.0,
            memory_used_gb=0.0,
            memory_total_gb=0.0,
            disk_percent=0.0,
            load_average=[0.0, 0.0, 0.0],
        )

        return HealthResponse(
            status=HealthStatus.DEGRADED,
            timestamp=datetime.utcnow(),
            version=__version__,
            uptime_seconds=round(uptime_seconds, 2),
            system=fallback_metrics,
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
                "vault_integration": True,
                "summarization": False,
            },
            app_name=settings.app_name,
        )

    def _determine_overall_status(
        self, checks: List[HealthCheck], services: Dict[str, HealthStatus]
    ) -> HealthStatus:
        """Determine overall health status based on checks and services."""
        # If any critical service is unhealthy, overall status is unhealthy
        critical_services = ["fastapi"]  # Add more as needed
        for service_name in critical_services:
            if services.get(service_name) == HealthStatus.UNHEALTHY:
                return HealthStatus.UNHEALTHY

        # If any check is unhealthy, overall status is unhealthy
        unhealthy_checks = [c for c in checks if c.status == HealthStatus.UNHEALTHY]
        if unhealthy_checks:
            return HealthStatus.UNHEALTHY

        # If any check or service is degraded, overall status is degraded
        degraded_checks = [c for c in checks if c.status == HealthStatus.DEGRADED]
        degraded_services = [s for s in services.values() if s == HealthStatus.DEGRADED]
        if degraded_checks or degraded_services:
            return HealthStatus.DEGRADED

        # All checks and services are healthy
        return HealthStatus.HEALTHY
