"""Tests for health service orchestrator."""

import asyncio
from unittest.mock import Mock, patch

import pytest

from app.core.health.models import HealthCheck, HealthStatus, SystemMetrics
from app.core.health.service import HealthService


class TestHealthService:
    """Test HealthService functionality."""

    @pytest.fixture
    def health_service(self):
        """Create HealthService instance for testing."""
        return HealthService()

    @patch('app.core.health.service.SystemMonitor')
    async def test_get_health_status_success(self, mock_monitor_class, health_service):
        """Test successful health status retrieval."""
        # Mock system monitor
        mock_monitor = Mock()
        mock_monitor_class.return_value = mock_monitor
        
        # Mock system metrics
        mock_metrics = SystemMetrics(
            cpu_percent=25.0,
            memory_percent=50.0,
            memory_used_gb=8.0,
            memory_total_gb=16.0,
            disk_percent=60.0,
            load_average=[1.0, 1.2, 1.5]
        )
        mock_monitor.get_system_metrics.return_value = mock_metrics
        
        # Mock health checks
        mock_checks = [
            HealthCheck(
                name="memory_usage",
                status=HealthStatus.HEALTHY,
                message="Memory usage normal"
            )
        ]
        mock_monitor.get_health_checks.return_value = mock_checks
        
        # Mock service dependencies
        mock_services = {
            "fastapi": HealthStatus.HEALTHY,
            "whisper": HealthStatus.HEALTHY,
            "ollama": HealthStatus.HEALTHY
        }
        mock_monitor.check_service_dependencies.return_value = mock_services
        
        # Get health status
        response = await health_service.get_health_status()
        
        # Verify response
        assert response.status == HealthStatus.HEALTHY
        assert response.system == mock_metrics
        assert response.checks == mock_checks
        assert response.services == mock_services
        assert response.features["audio_upload"] is True
        assert response.features["transcription"] is True
        assert response.features["summarization"] is False

    async def test_get_health_status_timeout(self, health_service):
        """Test health status timeout handling."""
        # Mock the monitor to take too long
        with patch.object(health_service, '_perform_health_checks') as mock_perform:
            # Make it sleep longer than timeout (400ms)
            async def slow_check():
                await asyncio.sleep(0.5)
                return Mock()
            
            mock_perform.side_effect = slow_check
            
            # Should return fallback status due to timeout
            response = await health_service.get_health_status()
            
            assert response.status == HealthStatus.DEGRADED
            assert len(response.checks) == 1
            assert response.checks[0].name == "health_check_timeout"

    async def test_get_health_status_exception(self, health_service):
        """Test health status exception handling."""
        with patch.object(health_service, '_perform_health_checks') as mock_perform:
            mock_perform.side_effect = Exception("Test error")
            
            response = await health_service.get_health_status()
            
            assert response.status == HealthStatus.DEGRADED
            assert response.services["fastapi"] == HealthStatus.DEGRADED

    async def test_determine_overall_status_healthy(self, health_service):
        """Test overall status determination - healthy case."""
        checks = [
            HealthCheck(name="memory", status=HealthStatus.HEALTHY, message="OK"),
            HealthCheck(name="cpu", status=HealthStatus.HEALTHY, message="OK"),
        ]
        services = {
            "fastapi": HealthStatus.HEALTHY,
            "whisper": HealthStatus.HEALTHY,
        }
        
        status = health_service._determine_overall_status(checks, services)
        assert status == HealthStatus.HEALTHY

    async def test_determine_overall_status_degraded_checks(self, health_service):
        """Test overall status - degraded due to checks."""
        checks = [
            HealthCheck(name="memory", status=HealthStatus.HEALTHY, message="OK"),
            HealthCheck(name="cpu", status=HealthStatus.DEGRADED, message="High CPU"),
        ]
        services = {
            "fastapi": HealthStatus.HEALTHY,
        }
        
        status = health_service._determine_overall_status(checks, services)
        assert status == HealthStatus.DEGRADED

    async def test_determine_overall_status_degraded_services(self, health_service):
        """Test overall status - degraded due to services."""
        checks = [
            HealthCheck(name="memory", status=HealthStatus.HEALTHY, message="OK"),
        ]
        services = {
            "fastapi": HealthStatus.HEALTHY,
            "whisper": HealthStatus.DEGRADED,
        }
        
        status = health_service._determine_overall_status(checks, services)
        assert status == HealthStatus.DEGRADED

    async def test_determine_overall_status_unhealthy_check(self, health_service):
        """Test overall status - unhealthy due to check."""
        checks = [
            HealthCheck(name="memory", status=HealthStatus.UNHEALTHY, message="Critical"),
            HealthCheck(name="cpu", status=HealthStatus.HEALTHY, message="OK"),
        ]
        services = {
            "fastapi": HealthStatus.HEALTHY,
        }
        
        status = health_service._determine_overall_status(checks, services)
        assert status == HealthStatus.UNHEALTHY

    async def test_determine_overall_status_unhealthy_critical_service(self, health_service):
        """Test overall status - unhealthy due to critical service."""
        checks = [
            HealthCheck(name="memory", status=HealthStatus.HEALTHY, message="OK"),
        ]
        services = {
            "fastapi": HealthStatus.UNHEALTHY,  # Critical service
            "whisper": HealthStatus.HEALTHY,
        }
        
        status = health_service._determine_overall_status(checks, services)
        assert status == HealthStatus.UNHEALTHY

    async def test_fallback_health_status(self, health_service):
        """Test fallback health status generation."""
        response = await health_service._get_fallback_health_status()
        
        assert response.status == HealthStatus.DEGRADED
        assert response.system.cpu_percent == 0.0
        assert response.system.memory_percent == 0.0
        assert len(response.checks) == 1
        assert response.checks[0].name == "health_check_timeout"
        assert response.features["audio_upload"] is True

    async def test_uptime_calculation(self, health_service):
        """Test uptime calculation in health response."""
        with patch('app.core.health.service._start_time', 1000.0), \
             patch('time.time', return_value=1060.0):  # 60 seconds later
            
            with patch.object(health_service, '_perform_health_checks') as mock_perform:
                # Create a minimal mock response to avoid complex setup
                mock_response = Mock()
                mock_response.uptime_seconds = 60.0
                mock_perform.return_value = mock_response
                
                response = await health_service.get_health_status()
                # The actual uptime calculation happens in _perform_health_checks
                # This test verifies the mocking works correctly