"""Integration tests for vault functionality."""

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.mark.integration
class TestVaultIntegration:
    """Test vault integration with full system."""

    async def test_full_pipeline_to_vault(self, client, tmp_path):
        """Test complete flow from upload to vault save."""
        # Setup test vault
        test_vault = tmp_path / "obsidian_vault"
        test_vault.mkdir()

        with patch("app.core.settings.settings.obsidian_vault_path", test_vault):
            # Re-initialize vault service with new path
            from app.services.vault import VaultService

            with patch("app.services.vault.vault_service", VaultService()):
                response = await client.post(
                    "/api/v1/vault/save",
                    json={
                        "upload_id": "integration_test",
                        "transcription": "This is an integration test transcription. It contains multiple sentences to test the full functionality of the vault saving system.",
                        "summary": "- Integration test completed successfully\n- Vault saving functionality verified",
                        "keywords": ["integration", "test", "vault", "obsidian"],
                        "metadata": {
                            "source": "integration_test",
                            "test_type": "full_pipeline",
                        },
                    },
                )

                assert response.status_code == 201
                data = response.json()

                # Verify file exists in vault
                saved_file = test_vault / data["filename"]
                assert saved_file.exists()

                # Verify content structure
                content = saved_file.read_text()
                assert "---" in content  # YAML frontmatter
                assert "type: voice-note" in content
                assert "tags:" in content
                assert "integration" in content
                assert "## Summary" in content
                assert "## Transcription" in content
                assert "This is an integration test transcription" in content

    async def test_health_check_includes_vault(self, client, tmp_path):
        """Test that health check includes vault status."""
        test_vault = tmp_path / "obsidian_vault"
        test_vault.mkdir()

        with patch("app.core.settings.settings.obsidian_vault_path", test_vault):
            # Re-initialize services
            from app.services.vault import VaultService

            with patch("app.services.vault.vault_service", VaultService()):
                response = await client.get("/health")

                assert response.status_code == 200
                data = response.json()

                # Check that vault is included in services
                assert "vault" in data.get("services", {})
                assert data["services"]["vault"] == "healthy"

                # Check that vault feature is enabled
                assert data.get("features", {}).get("vault_integration") is True

                # Check for vault-specific health checks
                checks = data.get("checks", [])
                vault_checks = [
                    c for c in checks if "vault" in c.get("name", "").lower()
                ]
                assert len(vault_checks) > 0

    async def test_vault_error_in_health_check(self, client):
        """Test health check when vault is not accessible."""
        # Use non-existent path
        with patch(
            "app.core.settings.settings.obsidian_vault_path", Path("/nonexistent/path")
        ):
            from app.services.vault import VaultService

            with patch("app.services.vault.vault_service", VaultService()):
                response = await client.get("/health")

                assert response.status_code == 200
                data = response.json()

                # Vault should be unhealthy
                assert data.get("services", {}).get("vault") == "unhealthy"

                # Overall status should be degraded or unhealthy
                assert data.get("status") in ["degraded", "unhealthy"]

    async def test_concurrent_vault_saves(self, client, tmp_path):
        """Test concurrent saves to vault."""
        test_vault = tmp_path / "obsidian_vault"
        test_vault.mkdir()

        with patch("app.core.settings.settings.obsidian_vault_path", test_vault):
            from app.services.vault import VaultService

            with patch("app.services.vault.vault_service", VaultService()):
                import asyncio

                # Create multiple concurrent save requests
                tasks = []
                for i in range(3):
                    task = client.post(
                        "/api/v1/vault/save",
                        json={
                            "upload_id": f"concurrent_test_{i}",
                            "transcription": f"This is concurrent test number {i}.",
                            "keywords": [f"test{i}", "concurrent"],
                        },
                    )
                    tasks.append(task)

                # Execute concurrently
                responses = await asyncio.gather(*tasks)

                # All should succeed
                for i, response in enumerate(responses):
                    assert response.status_code == 201
                    data = response.json()

                    # Verify file exists
                    saved_file = test_vault / data["filename"]
                    assert saved_file.exists()

                    # Verify content
                    content = saved_file.read_text()
                    assert f"concurrent test number {i}" in content

    async def test_vault_disk_space_monitoring(self, client, tmp_path):
        """Test vault disk space monitoring in health checks."""
        test_vault = tmp_path / "obsidian_vault"
        test_vault.mkdir()

        with patch("app.core.settings.settings.obsidian_vault_path", test_vault):
            from app.services.vault import VaultService

            vault_service = VaultService()

            # Mock low disk space
            with patch.object(vault_service, "get_vault_status") as mock_status:
                mock_status.return_value = {
                    "accessible": True,
                    "writable": True,
                    "free_space_gb": 0.5,  # Low disk space
                    "total_space_gb": 100.0,
                    "path": str(test_vault),
                }

                with patch("app.services.vault.vault_service", vault_service):
                    response = await client.get("/health")

                    assert response.status_code == 200
                    data = response.json()

                    # Should show degraded status due to low disk space
                    checks = data.get("checks", [])
                    storage_checks = [
                        c for c in checks if c.get("name") == "vault_storage"
                    ]

                    if storage_checks:
                        assert storage_checks[0]["status"] == "degraded"
                        assert "disk space" in storage_checks[0]["message"].lower()

    async def test_api_documentation_includes_vault(self, client):
        """Test that API documentation includes vault endpoints."""
        response = await client.get("/openapi.json")
        assert response.status_code == 200

        openapi_spec = response.json()

        # Check that vault endpoints are documented
        paths = openapi_spec.get("paths", {})
        assert "/api/v1/vault/save" in paths

        # Check vault tag exists
        tags = openapi_spec.get("tags", [])
        vault_tag = next((tag for tag in tags if tag.get("name") == "vault"), None)
        assert vault_tag is not None
        assert "vault" in vault_tag.get("description", "").lower()

    async def test_root_endpoint_includes_vault(self, client):
        """Test that root endpoint includes vault save endpoint."""
        response = await client.get("/")
        assert response.status_code == 200

        data = response.json()
        endpoints = data.get("endpoints", {})
        assert "vault_save" in endpoints
        assert endpoints["vault_save"] == "/api/v1/vault/save"

    async def test_vault_with_special_characters(self, client, tmp_path):
        """Test vault save with special characters in content."""
        test_vault = tmp_path / "obsidian_vault"
        test_vault.mkdir()

        with patch("app.core.settings.settings.obsidian_vault_path", test_vault):
            from app.services.vault import VaultService

            with patch("app.services.vault.vault_service", VaultService()):
                response = await client.post(
                    "/api/v1/vault/save",
                    json={
                        "upload_id": "special_chars_test",
                        "transcription": "This has special chars: åäö, émañá, 中文, 🎵♪♫",
                        "summary": "- Test with émojis 🎵\n- And spëcial chars",
                        "keywords": ["spëcial", "émojis", "tëst"],
                    },
                )

                assert response.status_code == 201
                data = response.json()

                # Verify file exists and content is preserved
                saved_file = test_vault / data["filename"]
                assert saved_file.exists()

                content = saved_file.read_text(encoding="utf-8")
                assert "åäö" in content
                assert "émañá" in content
                assert "中文" in content
                assert "🎵♪♫" in content
