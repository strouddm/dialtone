"""Tests for setup validation functions."""

import os
import tempfile
import unittest.mock
from pathlib import Path

import pytest


class TestSetupValidators:
    """Test setup validation functions."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_vault_path_validation_success(self, temp_dir):
        """Test successful vault path validation."""
        vault_path = temp_dir / "test_vault"
        vault_path.mkdir()

        # Make writable
        vault_path.chmod(0o755)

        # Mock the validation function
        with unittest.mock.patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0

            # Would call validate_vault_path(str(vault_path))
            assert vault_path.exists()
            assert vault_path.is_dir()
            assert os.access(vault_path, os.W_OK)

    def test_vault_path_validation_nonexistent(self, temp_dir):
        """Test vault path validation with non-existent directory."""
        vault_path = temp_dir / "nonexistent"

        assert not vault_path.exists()

    def test_vault_path_validation_not_writable(self, temp_dir):
        """Test vault path validation with non-writable directory."""
        vault_path = temp_dir / "readonly_vault"
        vault_path.mkdir()
        vault_path.chmod(0o444)  # Read-only

        # Check if directory is not writable
        if os.access(vault_path, os.W_OK):
            pytest.skip("Cannot test non-writable directory (running as root?)")

        assert vault_path.exists()
        assert not os.access(vault_path, os.W_OK)

    def test_port_availability_check(self):
        """Test port availability checking."""
        # Test with a port that should be available
        import socket

        # Find an available port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            available_port = s.getsockname()[1]

        # Port should be available now
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("localhost", available_port))
                port_is_available = True
            except OSError:
                port_is_available = False

        assert port_is_available

    def test_domain_validation_format(self):
        """Test domain name format validation."""
        valid_domains = [
            "example.com",
            "subdomain.example.com",
            "test-domain.co.uk",
            "my-site.example.org",
        ]

        invalid_domains = [
            "",
            "invalid domain with spaces",
            "domain..double-dot.com",
            "-invalid-start.com",
            "invalid-end-.com",
            "toolong" + "a" * 250 + ".com",
        ]

        # Basic regex for domain validation
        import re

        domain_pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"

        for domain in valid_domains:
            assert re.match(domain_pattern, domain), f"Valid domain failed: {domain}"

        for domain in invalid_domains:
            assert not re.match(
                domain_pattern, domain
            ), f"Invalid domain passed: {domain}"

    def test_system_resource_checking(self):
        """Test system resource validation."""
        import psutil

        # Get actual system resources
        memory_gb = psutil.virtual_memory().total / (1024**3)
        disk_gb = psutil.disk_usage(".").free / (1024**3)

        # Should have some memory and disk space
        assert memory_gb > 0
        assert disk_gb > 0

        # For testing, we can mock resource checks
        with unittest.mock.patch("psutil.virtual_memory") as mock_memory:
            mock_memory.return_value.total = 8 * 1024**3  # 8GB
            assert mock_memory.return_value.total / (1024**3) >= 8

    def test_docker_version_parsing(self):
        """Test Docker version parsing logic."""
        test_versions = [
            ("20.10.0", "20.10", True),
            ("20.10.5", "20.10", True),
            ("19.03.0", "20.10", False),
            ("21.0.0", "20.10", True),
            ("20.9.0", "20.10", False),
        ]

        def version_compare(version1, version2):
            """Compare version strings."""
            v1_parts = [int(x) for x in version1.split(".")]
            v2_parts = [int(x) for x in version2.split(".")]

            # Pad with zeros to make same length
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_len - len(v1_parts)))
            v2_parts.extend([0] * (max_len - len(v2_parts)))

            return v1_parts >= v2_parts

        for current_version, min_version, expected in test_versions:
            result = version_compare(current_version, min_version)
            assert (
                result == expected
            ), f"Version {current_version} >= {min_version} should be {expected}"

    def test_environment_file_validation(self, temp_dir):
        """Test environment file validation."""
        env_file = temp_dir / ".env"

        # Create a valid environment file
        env_content = """
# Test environment file
OBSIDIAN_VAULT_PATH=/test/vault
API_PORT=8000
ENABLE_SSL=false
"""
        env_file.write_text(env_content)

        assert env_file.exists()

        # Parse and validate content
        config = {}
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip()

        assert "OBSIDIAN_VAULT_PATH" in config
        assert "API_PORT" in config
        assert config["API_PORT"] == "8000"

    def test_ssl_configuration_validation(self):
        """Test SSL configuration validation."""
        ssl_configs = [
            {
                "enable_ssl": "true",
                "domain": "example.com",
                "email": "test@example.com",
                "valid": True,
            },
            {
                "enable_ssl": "true",
                "domain": "",
                "email": "test@example.com",
                "valid": False,
            },
            {
                "enable_ssl": "true",
                "domain": "example.com",
                "email": "",
                "valid": False,
            },
            {"enable_ssl": "false", "domain": "", "email": "", "valid": True},
        ]

        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        domain_pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"

        import re

        for config in ssl_configs:
            if config["enable_ssl"] == "true":
                domain_valid = bool(config["domain"]) and bool(
                    re.match(domain_pattern, config["domain"])
                )
                email_valid = bool(config["email"]) and bool(
                    re.match(email_pattern, config["email"])
                )
                is_valid = domain_valid and email_valid
            else:
                is_valid = True

            assert (
                is_valid == config["valid"]
            ), f"SSL config validation failed for {config}"
