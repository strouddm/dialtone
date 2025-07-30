"""Tests for system monitoring."""

import asyncio
from unittest.mock import Mock, patch

import pytest

from app.core.health.models import HealthStatus
from app.core.health.monitors import SystemMonitor


class TestSystemMonitor:
    """Test SystemMonitor functionality."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Clear cache before each test."""
        SystemMonitor.clear_cache()

    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    @patch('psutil.getloadavg')
    async def test_get_system_metrics_success(
        self, mock_loadavg, mock_disk, mock_memory, mock_cpu
    ):
        """Test successful system metrics collection."""
        # Mock psutil responses
        mock_cpu.return_value = 25.5
        mock_memory.return_value = Mock(
            percent=45.2,
            used=7 * 1024**3,  # 7GB in bytes
            total=16 * 1024**3  # 16GB in bytes
        )
        mock_disk.return_value = Mock(
            used=300 * 1024**3,  # 300GB used
            total=1000 * 1024**3  # 1TB total
        )
        mock_loadavg.return_value = [1.2, 1.5, 1.8]
        
        metrics = await SystemMonitor.get_system_metrics()
        
        assert metrics.cpu_percent == 25.5
        assert metrics.memory_percent == 45.2
        assert metrics.memory_used_gb == 7.0
        assert metrics.memory_total_gb == 16.0
        assert metrics.disk_percent == 30.0
        assert metrics.load_average == [1.2, 1.5, 1.8]

    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    @patch('psutil.getloadavg')
    async def test_get_system_metrics_windows_fallback(
        self, mock_loadavg, mock_disk, mock_memory, mock_cpu
    ):
        """Test Windows fallback for load average."""
        mock_cpu.return_value = 25.5
        mock_memory.return_value = Mock(
            percent=45.2,
            used=7 * 1024**3,
            total=16 * 1024**3
        )
        mock_disk.return_value = Mock(
            used=300 * 1024**3,
            total=1000 * 1024**3
        )
        # Simulate Windows - no getloadavg
        mock_loadavg.side_effect = AttributeError("No load average on Windows")
        
        metrics = await SystemMonitor.get_system_metrics()
        
        assert metrics.load_average == [0.0, 0.0, 0.0]

    @patch('psutil.cpu_percent', side_effect=Exception("psutil error"))
    async def test_get_system_metrics_error_fallback(self, mock_cpu):
        """Test error fallback for system metrics."""
        metrics = await SystemMonitor.get_system_metrics()
        
        # Should return fallback values
        assert metrics.cpu_percent == 0.0
        assert metrics.memory_percent == 0.0
        assert metrics.memory_used_gb == 0.0
        assert metrics.memory_total_gb == 0.0
        assert metrics.disk_percent == 0.0
        assert metrics.load_average == [0.0, 0.0, 0.0]

    async def test_get_system_metrics_caching(self):
        """Test that system metrics are cached properly."""
        with patch('psutil.cpu_percent', return_value=25.0) as mock_cpu, \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk, \
             patch('psutil.getloadavg', return_value=[1.0, 1.0, 1.0]):
            
            mock_memory.return_value = Mock(
                percent=50.0, used=8 * 1024**3, total=16 * 1024**3
            )
            mock_disk.return_value = Mock(
                used=400 * 1024**3, total=1000 * 1024**3
            )
            
            # First call should hit psutil
            metrics1 = await SystemMonitor.get_system_metrics()
            assert mock_cpu.call_count == 1
            
            # Second call should use cache
            metrics2 = await SystemMonitor.get_system_metrics()
            assert mock_cpu.call_count == 1  # Not called again
            
            # Results should be identical
            assert metrics1.cpu_percent == metrics2.cpu_percent
            assert metrics1.memory_percent == metrics2.memory_percent

    async def test_get_health_checks_healthy(self):
        """Test health checks with normal metrics."""
        from app.core.health.models import SystemMetrics
        
        metrics = SystemMetrics(
            cpu_percent=50.0,
            memory_percent=60.0,
            memory_used_gb=9.6,
            memory_total_gb=16.0,
            disk_percent=70.0,
            load_average=[1.0, 1.2, 1.5]
        )
        
        checks = await SystemMonitor.get_health_checks(metrics)
        
        # Should have 3 checks: memory, cpu, disk
        assert len(checks) == 3
        
        check_names = [c.name for c in checks]
        assert "memory_usage" in check_names
        assert "cpu_usage" in check_names
        assert "disk_usage" in check_names
        
        # All should be healthy
        for check in checks:
            assert check.status == HealthStatus.HEALTHY

    async def test_get_health_checks_degraded(self):
        """Test health checks with warning-level metrics."""
        from app.core.health.models import SystemMetrics
        
        metrics = SystemMetrics(
            cpu_percent=75.0,  # Above 70% threshold
            memory_percent=85.0,  # Above 80% threshold
            memory_used_gb=13.6,
            memory_total_gb=16.0,
            disk_percent=85.0,  # Above 80% threshold
            load_average=[2.0, 2.2, 2.5]
        )
        
        checks = await SystemMonitor.get_health_checks(metrics)
        
        # Find specific checks
        memory_check = next(c for c in checks if c.name == "memory_usage")
        cpu_check = next(c for c in checks if c.name == "cpu_usage")
        disk_check = next(c for c in checks if c.name == "disk_usage")
        
        assert memory_check.status == HealthStatus.DEGRADED
        assert cpu_check.status == HealthStatus.DEGRADED
        assert disk_check.status == HealthStatus.DEGRADED

    async def test_get_health_checks_unhealthy(self):
        """Test health checks with critical metrics."""
        from app.core.health.models import SystemMetrics
        
        metrics = SystemMetrics(
            cpu_percent=50.0,
            memory_percent=95.0,  # Above 90% critical threshold
            memory_used_gb=15.2,
            memory_total_gb=16.0,
            disk_percent=70.0,
            load_average=[1.0, 1.2, 1.5]
        )
        
        checks = await SystemMonitor.get_health_checks(metrics)
        
        memory_check = next(c for c in checks if c.name == "memory_usage")
        assert memory_check.status == HealthStatus.UNHEALTHY
        assert "critical" in memory_check.message.lower()

    async def test_check_service_dependencies(self):
        """Test service dependency checking."""
        services = await SystemMonitor.check_service_dependencies()
        
        # Should have all expected services
        assert "fastapi" in services
        assert "whisper" in services
        assert "ollama" in services
        
        # FastAPI should always be healthy if we're running
        assert services["fastapi"] == HealthStatus.HEALTHY
        
        # Future services should be marked appropriately
        assert services["whisper"] == HealthStatus.HEALTHY
        assert services["ollama"] == HealthStatus.HEALTHY

    def test_clear_cache(self):
        """Test cache clearing functionality."""
        # This is mainly for test cleanup, but verify it works
        SystemMonitor.clear_cache()
        # If no exception, cache clearing works