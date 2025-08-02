"""End-to-end voice processing workflow integration tests."""

import json
import pytest
from pathlib import Path
from typing import Dict, Any
from unittest.mock import AsyncMock, patch

from fastapi import status
from httpx import AsyncClient

from app.models.session import SessionStatus


@pytest.mark.integration
class TestVoiceProcessingWorkflow:
    """Test complete voice note processing workflows."""

    async def test_complete_voice_note_processing(
        self,
        async_client: AsyncClient,
        test_obsidian_vault: Path,
        test_audio_content: bytes,
        mock_whisper_service: AsyncMock,
        mock_ollama_service: AsyncMock,
        setup_test_environment: Dict[str, Path]
    ):
        """Test complete voice note processing pipeline from upload to vault save."""
        # Step 1: Upload audio file
        files = {"file": ("test_audio.webm", test_audio_content, "audio/webm")}
        data = {"description": "Integration test voice note"}
        
        upload_response = await async_client.post(
            "/api/v1/audio/upload",
            files=files,
            data=data
        )
        
        assert upload_response.status_code == status.HTTP_201_CREATED
        upload_data = upload_response.json()
        upload_id = upload_data["upload_id"]
        
        # Step 2: Process transcription
        transcription_response = await async_client.post(
            f"/api/v1/audio/{upload_id}/transcribe"
        )
        
        assert transcription_response.status_code == status.HTTP_200_OK
        transcription_data = transcription_response.json()
        assert "transcription" in transcription_data
        assert "text" in transcription_data["transcription"]
        
        # Step 3: Generate summary and keywords
        summary_response = await async_client.post(
            f"/api/v1/audio/{upload_id}/summarize"
        )
        
        assert summary_response.status_code == status.HTTP_200_OK
        summary_data = summary_response.json()
        assert "summary" in summary_data
        assert "keywords" in summary_data
        
        # Step 4: Save to Obsidian vault
        vault_response = await async_client.post(
            "/api/v1/vault/save",
            json={
                "upload_id": upload_id,
                "transcription": transcription_data["transcription"]["text"],
                "summary": summary_data["summary"],
                "keywords": summary_data["keywords"],
                "metadata": {
                    "source": "integration_test",
                    "description": "Integration test voice note"
                }
            }
        )
        
        assert vault_response.status_code == status.HTTP_201_CREATED
        vault_data = vault_response.json()
        assert "filename" in vault_data
        assert "file_path" in vault_data
        
        # Step 5: Verify file exists in vault
        vault_file = test_obsidian_vault / vault_data["filename"]
        assert vault_file.exists()
        
        # Verify file content structure
        content = vault_file.read_text()
        assert "---" in content  # YAML frontmatter
        assert "type: voice-note" in content
        assert "tags:" in content
        assert transcription_data["transcription"]["text"] in content
        assert summary_data["summary"] in content

    async def test_voice_workflow_with_session_management(
        self,
        async_client: AsyncClient,
        test_obsidian_vault: Path,
        test_audio_content: bytes,
        mock_whisper_service: AsyncMock,
        mock_ollama_service: AsyncMock,
        setup_test_environment: Dict[str, Path]
    ):
        """Test voice workflow with session management for multi-step editing."""
        # Step 1: Create session
        session_response = await async_client.post("/api/v1/sessions/")
        
        assert session_response.status_code == status.HTTP_201_CREATED
        session_data = session_response.json()
        session_id = session_data["session_id"]
        
        # Step 2: Upload audio with session
        files = {"file": ("test_audio.webm", test_audio_content, "audio/webm")}
        data = {
            "description": "Session-based voice note",
            "session_id": session_id
        }
        
        upload_response = await async_client.post(
            "/api/v1/audio/upload",
            files=files,
            data=data
        )
        
        assert upload_response.status_code == status.HTTP_201_CREATED
        upload_data = upload_response.json()
        upload_id = upload_data["upload_id"]
        
        # Step 3: Verify session state updated
        session_check_response = await async_client.get(f"/api/v1/sessions/{session_id}")
        assert session_check_response.status_code == status.HTTP_200_OK
        session_state = session_check_response.json()
        assert session_state["upload_id"] == upload_id
        assert session_state["status"] == SessionStatus.PROCESSING.value
        
        # Step 4: Process transcription
        transcription_response = await async_client.post(
            f"/api/v1/audio/{upload_id}/transcribe"
        )
        
        assert transcription_response.status_code == status.HTTP_200_OK
        
        # Step 5: Update session with custom edits
        edit_data = {
            "transcription": "Edited transcription for better accuracy",
            "summary": "- Custom edited summary\n- Integration test with session management",
            "keywords": ["edited", "session", "integration", "test"]
        }
        
        edit_response = await async_client.put(
            f"/api/v1/sessions/{session_id}/update",
            json=edit_data
        )
        
        assert edit_response.status_code == status.HTTP_200_OK
        
        # Step 6: Complete session and save to vault
        complete_response = await async_client.post(
            f"/api/v1/sessions/{session_id}/complete"
        )
        
        assert complete_response.status_code == status.HTTP_200_OK
        complete_data = complete_response.json()
        assert "filename" in complete_data
        
        # Verify final file contains edited content
        vault_file = test_obsidian_vault / complete_data["filename"]
        assert vault_file.exists()
        content = vault_file.read_text()
        assert "Edited transcription for better accuracy" in content
        assert "Custom edited summary" in content

    async def test_voice_workflow_error_recovery(
        self,
        async_client: AsyncClient,
        test_audio_content: bytes,
        setup_test_environment: Dict[str, Path]
    ):
        """Test error recovery in voice processing workflow."""
        # Step 1: Upload audio
        files = {"file": ("test_audio.webm", test_audio_content, "audio/webm")}
        data = {"description": "Error recovery test"}
        
        upload_response = await async_client.post(
            "/api/v1/audio/upload",
            files=files,
            data=data
        )
        
        assert upload_response.status_code == status.HTTP_201_CREATED
        upload_data = upload_response.json()
        upload_id = upload_data["upload_id"]
        
        # Step 2: Simulate transcription failure and recovery
        with patch("app.services.whisper_model.WhisperModel.transcribe") as mock_transcribe:
            # First call fails
            mock_transcribe.side_effect = Exception("Transcription service temporarily unavailable")
            
            transcription_response = await async_client.post(
                f"/api/v1/audio/{upload_id}/transcribe"
            )
            
            assert transcription_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            
            # Second call succeeds (recovery)
            mock_transcribe.side_effect = None
            mock_transcribe.return_value = {
                "text": "Recovered transcription after error",
                "segments": [{"start": 0.0, "end": 3.0, "text": "Recovered transcription after error"}]
            }
            
            retry_response = await async_client.post(
                f"/api/v1/audio/{upload_id}/transcribe"
            )
            
            assert retry_response.status_code == status.HTTP_200_OK
            retry_data = retry_response.json()
            assert "Recovered transcription after error" in retry_data["transcription"]["text"]

    async def test_concurrent_voice_processing(
        self,
        async_client: AsyncClient,
        test_audio_content: bytes,
        mock_whisper_service: AsyncMock,
        mock_ollama_service: AsyncMock,
        setup_test_environment: Dict[str, Path]
    ):
        """Test concurrent voice processing workflows."""
        import asyncio
        
        async def process_voice_note(note_id: int):
            """Process a single voice note."""
            files = {"file": (f"test_audio_{note_id}.webm", test_audio_content, "audio/webm")}
            data = {"description": f"Concurrent test voice note {note_id}"}
            
            # Upload
            upload_response = await async_client.post(
                "/api/v1/audio/upload",
                files=files,
                data=data
            )
            
            assert upload_response.status_code == status.HTTP_201_CREATED
            upload_data = upload_response.json()
            upload_id = upload_data["upload_id"]
            
            # Transcribe
            transcription_response = await async_client.post(
                f"/api/v1/audio/{upload_id}/transcribe"
            )
            
            assert transcription_response.status_code == status.HTTP_200_OK
            
            # Summarize
            summary_response = await async_client.post(
                f"/api/v1/audio/{upload_id}/summarize"
            )
            
            assert summary_response.status_code == status.HTTP_200_OK
            
            return upload_id
        
        # Process 3 concurrent voice notes
        tasks = [process_voice_note(i) for i in range(3)]
        upload_ids = await asyncio.gather(*tasks)
        
        # Verify all uploads completed successfully
        assert len(upload_ids) == 3
        assert all(upload_id for upload_id in upload_ids)

    async def test_voice_workflow_with_editing(
        self,
        async_client: AsyncClient,
        test_obsidian_vault: Path,
        test_audio_content: bytes,
        mock_whisper_service: AsyncMock,
        mock_ollama_service: AsyncMock,
        setup_test_environment: Dict[str, Path]
    ):
        """Test voice workflow with editing capabilities before saving."""
        # Step 1: Create session for editing workflow
        session_response = await async_client.post("/api/v1/sessions/")
        session_data = session_response.json()
        session_id = session_data["session_id"]
        
        # Step 2: Upload and process audio
        files = {"file": ("test_audio.webm", test_audio_content, "audio/webm")}
        data = {"session_id": session_id, "description": "Editing workflow test"}
        
        upload_response = await async_client.post(
            "/api/v1/audio/upload",
            files=files,
            data=data
        )
        upload_data = upload_response.json()
        upload_id = upload_data["upload_id"]
        
        # Process transcription and summary
        await async_client.post(f"/api/v1/audio/{upload_id}/transcribe")
        await async_client.post(f"/api/v1/audio/{upload_id}/summarize")
        
        # Step 3: Get session state for editing
        session_get_response = await async_client.get(f"/api/v1/sessions/{session_id}")
        session_state = session_get_response.json()
        
        # Step 4: Edit transcription
        original_transcription = session_state["transcription"]
        edited_transcription = f"EDITED: {original_transcription}"
        
        edit_response = await async_client.put(
            f"/api/v1/sessions/{session_id}/update",
            json={"transcription": edited_transcription}
        )
        
        assert edit_response.status_code == status.HTTP_200_OK
        
        # Step 5: Edit summary and keywords
        custom_summary = "- Comprehensive integration test\n- Editing workflow verification\n- Session management validation"
        custom_keywords = ["comprehensive", "editing", "workflow", "integration"]
        
        edit_summary_response = await async_client.put(
            f"/api/v1/sessions/{session_id}/update",
            json={
                "summary": custom_summary,
                "keywords": custom_keywords
            }
        )
        
        assert edit_summary_response.status_code == status.HTTP_200_OK
        
        # Step 6: Complete and save
        complete_response = await async_client.post(f"/api/v1/sessions/{session_id}/complete")
        assert complete_response.status_code == status.HTTP_200_OK
        
        complete_data = complete_response.json()
        vault_file = test_obsidian_vault / complete_data["filename"]
        content = vault_file.read_text()
        
        # Verify edited content is saved
        assert edited_transcription in content
        assert custom_summary in content
        assert "comprehensive" in content  # Check custom keyword

    async def test_voice_workflow_performance_validation(
        self,
        async_client: AsyncClient,
        test_audio_content: bytes,
        mock_whisper_service: AsyncMock,
        mock_ollama_service: AsyncMock,
        setup_test_environment: Dict[str, Path]
    ):
        """Test voice workflow meets performance requirements."""
        import time
        
        start_time = time.time()
        
        # Upload
        files = {"file": ("test_audio.webm", test_audio_content, "audio/webm")}
        upload_response = await async_client.post(
            "/api/v1/audio/upload",
            files=files,
            data={"description": "Performance test"}
        )
        upload_data = upload_response.json()
        upload_id = upload_data["upload_id"]
        
        # Process (transcribe + summarize)
        await async_client.post(f"/api/v1/audio/{upload_id}/transcribe")
        await async_client.post(f"/api/v1/audio/{upload_id}/summarize")
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Performance assertion: Should complete in reasonable time
        # Note: With mocked services, this tests API overhead only
        assert processing_time < 5.0  # 5 seconds for mocked services
        
        # Verify response times are within API requirements
        assert upload_response.elapsed.total_seconds() < 0.5  # <500ms per PRD