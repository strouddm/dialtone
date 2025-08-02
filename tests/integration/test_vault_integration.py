"""Integration tests for vault functionality."""

import asyncio
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch, AsyncMock

import pytest
from httpx import AsyncClient


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

    async def test_vault_markdown_formatting_compliance(
        self,
        async_client: AsyncClient,
        test_obsidian_vault: Path,
        setup_test_environment: Dict[str, Any]
    ):
        """Test vault saves comply with Obsidian markdown formatting."""
        vault_response = await async_client.post(
            "/api/v1/vault/save",
            json={
                "upload_id": "formatting_test",
                "transcription": "This is a test transcription with multiple sentences. It includes proper punctuation and capitalization.",
                "summary": "- First summary point with **bold** text\n- Second point with *italic* emphasis\n- Third point with `code` formatting",
                "keywords": ["formatting", "markdown", "obsidian", "test"],
                "metadata": {
                    "source": "integration_test",
                    "duration": 45.2,
                    "confidence": 0.95
                }
            }
        )
        
        assert vault_response.status_code == 201
        vault_data = vault_response.json()
        
        vault_file = test_obsidian_vault / vault_data["filename"]
        content = vault_file.read_text()
        
        # Verify YAML frontmatter structure
        assert content.startswith("---\n")
        frontmatter_end = content.find("\n---\n", 4)
        assert frontmatter_end > 0
        
        frontmatter = content[4:frontmatter_end]
        
        # Verify required frontmatter fields
        assert "type: voice-note" in frontmatter
        assert "created:" in frontmatter
        assert "tags:" in frontmatter
        assert "- formatting" in frontmatter
        assert "source: integration_test" in frontmatter
        assert "duration: 45.2" in frontmatter
        assert "confidence: 0.95" in frontmatter
        
        # Verify markdown structure
        body = content[frontmatter_end + 5:]  # Skip "---\n"
        assert "## Summary" in body
        assert "## Transcription" in body
        
        # Verify markdown formatting is preserved
        assert "**bold**" in body
        assert "*italic*" in body
        assert "`code`" in body

    async def test_vault_file_naming_conventions(
        self,
        async_client: AsyncClient,
        test_obsidian_vault: Path,
        setup_test_environment: Dict[str, Any]
    ):
        """Test vault file naming follows Obsidian conventions."""
        # Test with various upload IDs and metadata
        test_cases = [
            {
                "upload_id": "simple_test",
                "title": "Simple Test Note"
            },
            {
                "upload_id": "complex_test_123",
                "title": "Complex Test with Numbers"
            },
            {
                "upload_id": "special_chars_test",
                "title": "Test with Special Characters: åäö"
            }
        ]
        
        for case in test_cases:
            vault_response = await async_client.post(
                "/api/v1/vault/save",
                json={
                    "upload_id": case["upload_id"],
                    "transcription": f"Test transcription for {case['title']}",
                    "summary": f"- Summary for {case['title']}",
                    "keywords": ["test", "naming"],
                    "metadata": {"title": case["title"]}
                }
            )
            
            assert vault_response.status_code == 201
            vault_data = vault_response.json()
            filename = vault_data["filename"]
            
            # Verify filename conventions
            assert filename.endswith(".md")
            assert " " not in filename  # No spaces in filenames
            assert len(filename) <= 255  # Reasonable filename length
            
            # Verify file exists and is readable
            vault_file = test_obsidian_vault / filename
            assert vault_file.exists()
            assert vault_file.is_file()

    async def test_vault_concurrent_saves_with_collision_handling(
        self,
        async_client: AsyncClient,
        test_obsidian_vault: Path,
        setup_test_environment: Dict[str, Any]
    ):
        """Test concurrent vault saves with potential filename collisions."""
        async def save_voice_note(note_id: int):
            """Save a voice note and return the result."""
            vault_response = await async_client.post(
                "/api/v1/vault/save",
                json={
                    "upload_id": f"collision_test_{note_id}",
                    "transcription": f"Concurrent save test {note_id}",
                    "summary": f"- Test note {note_id}",
                    "keywords": ["concurrent", "test", f"note{note_id}"]
                }
            )
            
            return {
                "note_id": note_id,
                "status_code": vault_response.status_code,
                "filename": vault_response.json().get("filename") if vault_response.status_code == 201 else None
            }
        
        # Create 10 concurrent save tasks
        save_tasks = [save_voice_note(i) for i in range(10)]
        results = await asyncio.gather(*save_tasks)
        
        # Verify all saves succeeded
        successful_saves = [r for r in results if r["status_code"] == 201]
        assert len(successful_saves) == 10
        
        # Verify all filenames are unique (no collisions)
        filenames = [r["filename"] for r in successful_saves]
        assert len(set(filenames)) == len(filenames)  # All unique
        
        # Verify all files exist
        for result in successful_saves:
            vault_file = test_obsidian_vault / result["filename"]
            assert vault_file.exists()
            content = vault_file.read_text()
            assert f"Concurrent save test {result['note_id']}" in content

    async def test_vault_large_content_handling(
        self,
        async_client: AsyncClient,
        test_obsidian_vault: Path,
        setup_test_environment: Dict[str, Any]
    ):
        """Test vault handling of large transcriptions and summaries."""
        # Create large content
        large_transcription = " ".join([
            f"This is sentence {i} of a very long transcription that tests the system's ability to handle large amounts of text content."
            for i in range(200)
        ])
        
        large_summary = "\n".join([
            f"- Summary point {i} with detailed explanation and context"
            for i in range(50)
        ])
        
        vault_response = await async_client.post(
            "/api/v1/vault/save",
            json={
                "upload_id": "large_content_test",
                "transcription": large_transcription,
                "summary": large_summary,
                "keywords": ["large", "content", "test", "performance"],
                "metadata": {
                    "transcription_length": len(large_transcription),
                    "summary_length": len(large_summary)
                }
            }
        )
        
        assert vault_response.status_code == 201
        vault_data = vault_response.json()
        
        vault_file = test_obsidian_vault / vault_data["filename"]
        assert vault_file.exists()
        
        content = vault_file.read_text()
        
        # Verify large content is properly saved
        assert large_transcription in content
        assert large_summary in content
        assert f"transcription_length: {len(large_transcription)}" in content
        
        # Verify file size is reasonable
        file_size = vault_file.stat().st_size
        assert file_size > 10000  # Should be a large file
        assert file_size < 1024 * 1024  # But not unreasonably large

    async def test_vault_obsidian_link_generation(
        self,
        async_client: AsyncClient,
        test_obsidian_vault: Path,
        setup_test_environment: Dict[str, Any]
    ):
        """Test generation of Obsidian-compatible internal links."""
        # Create a note with references
        vault_response = await async_client.post(
            "/api/v1/vault/save",
            json={
                "upload_id": "link_test",
                "transcription": "This note references other concepts that could be linked in Obsidian.",
                "summary": "- Contains potential link targets\n- Tests Obsidian compatibility",
                "keywords": ["obsidian", "links", "references", "connections"],
                "metadata": {
                    "related_topics": ["AI", "voice processing", "note taking"]
                }
            }
        )
        
        assert vault_response.status_code == 201
        vault_data = vault_response.json()
        
        vault_file = test_obsidian_vault / vault_data["filename"]
        content = vault_file.read_text()
        
        # Verify Obsidian-compatible structure
        assert "tags:" in content
        assert "- obsidian" in content
        assert "related_topics:" in content
        
        # Check that content is ready for linking
        # (Obsidian will automatically detect potential links)
        assert "AI" in content
        assert "voice processing" in content
        assert "note taking" in content

    async def test_vault_backup_and_recovery_simulation(
        self,
        async_client: AsyncClient,
        test_obsidian_vault: Path,
        setup_test_environment: Dict[str, Any]
    ):
        """Test vault operations with simulated backup/recovery scenarios."""
        # Create initial notes
        initial_notes = []
        for i in range(3):
            vault_response = await async_client.post(
                "/api/v1/vault/save",
                json={
                    "upload_id": f"backup_test_{i}",
                    "transcription": f"Initial note {i} for backup testing",
                    "summary": f"- Backup test note {i}",
                    "keywords": ["backup", "test", f"note{i}"]
                }
            )
            assert vault_response.status_code == 201
            initial_notes.append(vault_response.json())
        
        # Verify all files exist
        for note in initial_notes:
            vault_file = test_obsidian_vault / note["filename"]
            assert vault_file.exists()
        
        # Simulate backup by copying files
        backup_dir = test_obsidian_vault.parent / "backup"
        backup_dir.mkdir()
        
        for note in initial_notes:
            source_file = test_obsidian_vault / note["filename"]
            backup_file = backup_dir / note["filename"]
            backup_file.write_text(source_file.read_text())
        
        # Simulate data loss (remove original files)
        for note in initial_notes:
            vault_file = test_obsidian_vault / note["filename"]
            vault_file.unlink()
        
        # Verify files are gone
        for note in initial_notes:
            vault_file = test_obsidian_vault / note["filename"]
            assert not vault_file.exists()
        
        # Simulate recovery (restore from backup)
        for note in initial_notes:
            backup_file = backup_dir / note["filename"]
            restored_file = test_obsidian_vault / note["filename"]
            restored_file.write_text(backup_file.read_text())
        
        # Verify recovery successful
        for note in initial_notes:
            vault_file = test_obsidian_vault / note["filename"]
            assert vault_file.exists()
            content = vault_file.read_text()
            note_id = note["filename"].split("_")[-1].split(".")[0]
            assert f"Initial note {note_id}" in content
