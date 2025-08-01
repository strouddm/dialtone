"""System monitoring implementations."""

import asyncio
import logging
import time
from typing import Dict, List

import psutil

from .models import HealthCheck, HealthStatus, SystemMetrics

logger = logging.getLogger(__name__)

# System health thresholds
MEMORY_WARNING_THRESHOLD = 80  # 80% of available memory
MEMORY_CRITICAL_THRESHOLD = 90  # 90% of available memory
CPU_WARNING_THRESHOLD = 70  # 70% CPU usage
DISK_WARNING_THRESHOLD = 80  # 80% disk usage

# Cache settings
CACHE_DURATION = 30  # 30 seconds
_cache: Dict[str, Dict] = {}


class SystemMonitor:
    """System resource monitoring with caching."""

    @staticmethod
    async def get_system_metrics() -> SystemMetrics:
        """Get current system resource usage with caching."""
        cache_key = "system_metrics"
        now = time.time()

        # Check cache
        if cache_key in _cache:
            cached_data = _cache[cache_key]
            if now - cached_data["timestamp"] < CACHE_DURATION:
                return SystemMetrics(**cached_data["data"])

        # Get fresh metrics
        try:
            # Run CPU-intensive operations in thread pool
            loop = asyncio.get_event_loop()

            # Get CPU usage (1 second sample)
            cpu_percent = await loop.run_in_executor(
                None, lambda: psutil.cpu_percent(interval=0.1)
            )

            # Get memory info
            memory = psutil.virtual_memory()
            memory_used_gb = memory.used / (1024**3)
            memory_total_gb = memory.total / (1024**3)

            # Get disk usage for root partition
            disk = psutil.disk_usage("/")
            disk_percent = (disk.used / disk.total) * 100

            # Get load average (Unix systems)
            try:
                load_avg = list(psutil.getloadavg())
            except AttributeError:
                # Windows doesn't have load average
                load_avg = [0.0, 0.0, 0.0]

            metrics_data = {
                "cpu_percent": round(cpu_percent, 1),
                "memory_percent": round(memory.percent, 1),
                "memory_used_gb": round(memory_used_gb, 2),
                "memory_total_gb": round(memory_total_gb, 2),
                "disk_percent": round(disk_percent, 1),
                "load_average": [round(avg, 2) for avg in load_avg],
            }

            # Cache the result
            _cache[cache_key] = {"timestamp": now, "data": metrics_data}

            return SystemMetrics(**metrics_data)

        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            # Return fallback metrics
            return SystemMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used_gb=0.0,
                memory_total_gb=0.0,
                disk_percent=0.0,
                load_average=[0.0, 0.0, 0.0],
            )

    @staticmethod
    async def get_health_checks(metrics: SystemMetrics) -> List[HealthCheck]:
        """Generate health checks based on system metrics."""
        checks = []

        # Memory usage check
        if metrics.memory_percent >= MEMORY_CRITICAL_THRESHOLD:
            checks.append(
                HealthCheck(
                    name="memory_usage",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Memory usage critical: {metrics.memory_percent}% (>{MEMORY_CRITICAL_THRESHOLD}%)",
                )
            )
        elif metrics.memory_percent >= MEMORY_WARNING_THRESHOLD:
            checks.append(
                HealthCheck(
                    name="memory_usage",
                    status=HealthStatus.DEGRADED,
                    message=f"Memory usage high: {metrics.memory_percent}% (>{MEMORY_WARNING_THRESHOLD}%)",
                )
            )
        else:
            checks.append(
                HealthCheck(
                    name="memory_usage",
                    status=HealthStatus.HEALTHY,
                    message=f"Memory usage normal: {metrics.memory_percent}%",
                )
            )

        # CPU usage check
        if metrics.cpu_percent >= CPU_WARNING_THRESHOLD:
            checks.append(
                HealthCheck(
                    name="cpu_usage",
                    status=HealthStatus.DEGRADED,
                    message=f"CPU usage high: {metrics.cpu_percent}% (>{CPU_WARNING_THRESHOLD}%)",
                )
            )
        else:
            checks.append(
                HealthCheck(
                    name="cpu_usage",
                    status=HealthStatus.HEALTHY,
                    message=f"CPU usage normal: {metrics.cpu_percent}%",
                )
            )

        # Disk usage check
        if metrics.disk_percent >= DISK_WARNING_THRESHOLD:
            checks.append(
                HealthCheck(
                    name="disk_usage",
                    status=HealthStatus.DEGRADED,
                    message=f"Disk usage high: {metrics.disk_percent}% (>{DISK_WARNING_THRESHOLD}%)",
                )
            )
        else:
            checks.append(
                HealthCheck(
                    name="disk_usage",
                    status=HealthStatus.HEALTHY,
                    message=f"Disk usage normal: {metrics.disk_percent}%",
                )
            )

        return checks

    @staticmethod
    async def check_service_dependencies() -> Dict[str, HealthStatus]:
        """Check status of service dependencies."""
        services = {
            "fastapi": HealthStatus.HEALTHY,  # Always healthy if we're responding
        }

        # Check Whisper service (already implemented)
        services["whisper"] = HealthStatus.HEALTHY  # Whisper is locally loaded

        # Check Ollama service
        try:
            from app.services.ollama import ollama_service
            
            if not ollama_service.enabled:
                services["ollama"] = HealthStatus.DEGRADED
            else:
                # Check if Ollama is responsive
                is_healthy = await ollama_service.health_check()
                services["ollama"] = HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY
        except Exception as e:
            logger.warning(f"Failed to check Ollama service: {e}")
            services["ollama"] = HealthStatus.UNHEALTHY

        return services

    @staticmethod
    def clear_cache() -> None:
        """Clear monitoring cache (useful for testing)."""
        global _cache
        _cache.clear()
