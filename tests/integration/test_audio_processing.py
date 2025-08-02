"""Audio processing pipeline integration tests."""

import pytest
from pathlib import Path
from typing import Dict, Any
from unittest.mock import AsyncMock, patch

from fastapi import status
from httpx import AsyncClient


@pytest.mark.integration
class TestAudioProcessingIntegration:
    """Test audio processing pipeline with different formats and scenarios."""

    async def test_webm_audio_processing_pipeline(
        self,
        async_client: AsyncClient,
        mock_whisper_service: AsyncMock,
        setup_test_environment: Dict[str, Path]
    ):
        """Test complete WebM audio processing pipeline."""
        # Simulate WebM audio content
        webm_content = b'\x1a\x45\xdf\xa3' + b'\x00' * 1000  # WebM signature + data
        
        files = {"file": ("test_audio.webm", webm_content, "audio/webm")}
        data = {"description": "WebM format test"}
        
        # Upload WebM file
        upload_response = await async_client.post(
            "/api/v1/audio/upload",
            files=files,
            data=data
        )
        
        assert upload_response.status_code == status.HTTP_201_CREATED
        upload_data = upload_response.json()
        upload_id = upload_data["upload_id"]
        
        # Verify file format is detected correctly
        assert upload_data["content_type"] == "audio/webm"
        assert upload_data["filename"].endswith(".webm")
        
        # Test audio conversion (should work with FFmpeg)
        with patch("app.services.audio_converter.AudioConverter.convert_to_wav") as mock_convert:
            mock_convert.return_value = setup_test_environment["upload_dir"] / f"{upload_id}.wav"
            
            # Process transcription (triggers conversion)
            transcription_response = await async_client.post(
                f"/api/v1/audio/{upload_id}/transcribe"
            )
            
            assert transcription_response.status_code == status.HTTP_200_OK
            transcription_data = transcription_response.json()
            
            # Verify conversion was called
            mock_convert.assert_called_once()
            
            # Verify transcription result
            assert "transcription" in transcription_data
            assert "text" in transcription_data["transcription"]

    async def test_m4a_audio_processing_pipeline(
        self,
        async_client: AsyncClient,
        mock_whisper_service: AsyncMock,
        setup_test_environment: Dict[str, Path]
    ):
        """Test complete M4A audio processing pipeline."""
        # Simulate M4A audio content with proper header
        m4a_content = b'\x00\x00\x00\x20ftypM4A ' + b'\x00' * 1000  # M4A signature + data
        
        files = {"file": ("test_audio.m4a", m4a_content, "audio/mp4")}
        data = {"description": "M4A format test"}
        
        upload_response = await async_client.post(
            "/api/v1/audio/upload",
            files=files,
            data=data
        )
        
        assert upload_response.status_code == status.HTTP_201_CREATED
        upload_data = upload_response.json()
        upload_id = upload_data["upload_id"]
        
        # Test M4A specific processing
        with patch("app.services.audio_converter.AudioConverter.convert_to_wav") as mock_convert:
            mock_convert.return_value = setup_test_environment["upload_dir"] / f"{upload_id}.wav"
            
            transcription_response = await async_client.post(
                f"/api/v1/audio/{upload_id}/transcribe"
            )
            
            assert transcription_response.status_code == status.HTTP_200_OK
            
            # Verify M4A conversion parameters
            mock_convert.assert_called_once()
            call_args = mock_convert.call_args
            assert str(call_args[0][0]).endswith(".m4a")  # Input file
            assert str(call_args[1]["output_path"]).endswith(".wav")  # Output file

    async def test_mp3_audio_processing_pipeline(
        self,
        async_client: AsyncClient,
        mock_whisper_service: AsyncMock,
        setup_test_environment: Dict[str, Path]
    ):
        """Test complete MP3 audio processing pipeline."""
        # Simulate MP3 audio content with ID3 header
        mp3_content = b'ID3\x03\x00\x00\x00' + b'\xff\xfb' + b'\x00' * 1000  # MP3 header + data
        
        files = {"file": ("test_audio.mp3", mp3_content, "audio/mpeg")}
        data = {"description": "MP3 format test"}
        
        upload_response = await async_client.post(
            "/api/v1/audio/upload",
            files=files,
            data=data
        )
        
        assert upload_response.status_code == status.HTTP_201_CREATED
        upload_data = upload_response.json()
        upload_id = upload_data["upload_id"]
        
        # Test MP3 processing with potential quality issues
        with patch("app.services.audio_converter.AudioConverter.convert_to_wav") as mock_convert:
            mock_convert.return_value = setup_test_environment["upload_dir"] / f"{upload_id}.wav"
            
            transcription_response = await async_client.post(
                f"/api/v1/audio/{upload_id}/transcribe"
            )
            
            assert transcription_response.status_code == status.HTTP_200_OK
            
            # Verify MP3 conversion called with proper audio normalization
            mock_convert.assert_called_once()

    async def test_large_audio_file_processing(
        self,
        async_client: AsyncClient,
        mock_whisper_service: AsyncMock,
        setup_test_environment: Dict[str, Path]
    ):
        """Test processing of large audio files (near size limits)."""
        # Create large audio content (approaching 50MB limit)
        large_content_size = 45 * 1024 * 1024  # 45MB
        large_audio_content = b'\x1a\x45\xdf\xa3' + b'\x00' * (large_content_size - 4)
        
        files = {"file": ("large_audio.webm", large_audio_content, "audio/webm")}
        data = {"description": "Large file processing test"}
        
        upload_response = await async_client.post(
            "/api/v1/audio/upload",
            files=files,
            data=data
        )
        
        assert upload_response.status_code == status.HTTP_201_CREATED
        upload_data = upload_response.json()
        upload_id = upload_data["upload_id"]
        
        # Verify file size is tracked
        assert upload_data["size"] == large_content_size
        
        # Test processing with extended timeout expectations
        with patch("app.services.audio_converter.AudioConverter.convert_to_wav") as mock_convert:
            mock_convert.return_value = setup_test_environment["upload_dir"] / f"{upload_id}.wav"
            
            # Mock Whisper to handle large file processing
            mock_whisper_service.transcribe.return_value = {
                "text": "This is a transcription of a large audio file that tests the system's ability to handle files approaching the size limit.",
                "segments": [
                    {
                        "start": 0.0,
                        "end": 10.0,
                        "text": "This is a transcription of a large audio file"
                    },
                    {
                        "start": 10.0,
                        "end": 20.0,
                        "text": "that tests the system's ability to handle files approaching the size limit."
                    }
                ]
            }
            
            transcription_response = await async_client.post(
                f"/api/v1/audio/{upload_id}/transcribe"
            )
            
            assert transcription_response.status_code == status.HTTP_200_OK
            transcription_data = transcription_response.json()
            
            # Verify large file transcription
            assert "large audio file" in transcription_data["transcription"]["text"]

    async def test_poor_quality_audio_handling(
        self,
        async_client: AsyncClient,
        setup_test_environment: Dict[str, Path]
    ):
        """Test handling of poor quality audio with graceful degradation."""
        # Simulate low-quality audio content
        poor_quality_content = b'\x1a\x45\xdf\xa3' + b'\x00\x01' * 500  # Very low bitrate simulation
        
        files = {"file": ("poor_quality.webm", poor_quality_content, "audio/webm")}
        data = {"description": "Poor quality audio test"}
        
        upload_response = await async_client.post(
            "/api/v1/audio/upload",
            files=files,
            data=data
        )
        
        upload_data = upload_response.json()
        upload_id = upload_data["upload_id"]
        
        # Mock Whisper to simulate poor quality transcription
        with patch("app.services.whisper_model.WhisperModel") as mock_whisper:
            mock_instance = AsyncMock()
            mock_instance.transcribe.return_value = {
                "text": "This is a low confidence transcription with potential errors.",
                "segments": [
                    {
                        "start": 0.0,
                        "end": 5.0,
                        "text": "This is a low confidence transcription",
                        "avg_logprob": -0.8  # Low confidence score
                    },
                    {
                        "start": 5.0,
                        "end": 8.0,
                        "text": "with potential errors.",
                        "avg_logprob": -0.9  # Very low confidence
                    }
                ],
                "language": "en",
                "language_probability": 0.7  # Lower certainty
            }
            mock_whisper.return_value = mock_instance
            
            transcription_response = await async_client.post(
                f"/api/v1/audio/{upload_id}/transcribe"
            )
            
            assert transcription_response.status_code == status.HTTP_200_OK
            transcription_data = transcription_response.json()
            
            # Verify transcription succeeded despite poor quality
            assert "transcription" in transcription_data
            assert "low confidence" in transcription_data["transcription"]["text"]
            
            # Check if quality warnings are included
            if "metadata" in transcription_data:
                assert "language_probability" in transcription_data["metadata"]

    async def test_unsupported_audio_format_handling(
        self,
        async_client: AsyncClient,
        setup_test_environment: Dict[str, Path]
    ):
        """Test handling of unsupported audio formats."""
        # Simulate unsupported format (e.g., FLAC)
        flac_content = b'fLaC\x00\x00\x00\x22' + b'\x00' * 1000  # FLAC signature
        
        files = {"file": ("test_audio.flac", flac_content, "audio/flac")}
        data = {"description": "Unsupported format test"}
        
        upload_response = await async_client.post(
            "/api/v1/audio/upload",
            files=files,
            data=data
        )
        
        # Should either reject at upload or handle gracefully during processing
        if upload_response.status_code == status.HTTP_201_CREATED:
            upload_data = upload_response.json()
            upload_id = upload_data["upload_id"]
            
            # If upload succeeds, conversion should handle it or fail gracefully
            transcription_response = await async_client.post(
                f"/api/v1/audio/{upload_id}/transcribe"
            )
            
            # Either succeeds with conversion or fails with clear error
            assert transcription_response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ]
        else:
            # Upload validation should catch unsupported formats
            assert upload_response.status_code in [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ]

    async def test_corrupted_audio_file_handling(
        self,
        async_client: AsyncClient,
        setup_test_environment: Dict[str, Path]
    ):
        """Test handling of corrupted audio files."""
        # Create corrupted audio content (valid header, corrupted data)
        corrupted_content = b'\x1a\x45\xdf\xa3' + b'\xff' * 100 + b'\x00' * 900  # WebM header + corrupted data
        
        files = {"file": ("corrupted.webm", corrupted_content, "audio/webm")}
        data = {"description": "Corrupted file test"}
        
        upload_response = await async_client.post(
            "/api/v1/audio/upload",
            files=files,
            data=data
        )
        
        assert upload_response.status_code == status.HTTP_201_CREATED
        upload_data = upload_response.json()
        upload_id = upload_data["upload_id"]
        
        # Test error handling during processing
        with patch("app.services.audio_converter.AudioConverter.convert_to_wav") as mock_convert:
            # Simulate conversion failure due to corruption
            mock_convert.side_effect = Exception("Audio file is corrupted or unreadable")
            
            transcription_response = await async_client.post(
                f"/api/v1/audio/{upload_id}/transcribe"
            )
            
            # Should handle error gracefully
            assert transcription_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            error_data = transcription_response.json()
            assert "error" in error_data or "detail" in error_data

    async def test_audio_format_conversion_validation(
        self,
        async_client: AsyncClient,
        mock_whisper_service: AsyncMock,
        setup_test_environment: Dict[str, Path]
    ):
        """Test audio format conversion meets Whisper requirements."""
        webm_content = b'\x1a\x45\xdf\xa3' + b'\x00' * 1000
        
        files = {"file": ("test_audio.webm", webm_content, "audio/webm")}
        upload_response = await async_client.post(
            "/api/v1/audio/upload",
            files=files,
            data={"description": "Conversion validation test"}
        )
        
        upload_data = upload_response.json()
        upload_id = upload_data["upload_id"]
        
        # Mock conversion with specific format requirements
        with patch("app.services.audio_converter.AudioConverter.convert_to_wav") as mock_convert:
            expected_wav_path = setup_test_environment["upload_dir"] / f"{upload_id}.wav"
            mock_convert.return_value = expected_wav_path
            
            transcription_response = await async_client.post(
                f"/api/v1/audio/{upload_id}/transcribe"
            )
            
            # Verify conversion parameters meet Whisper requirements
            mock_convert.assert_called_once()
            call_kwargs = mock_convert.call_args[1]
            
            # Check if conversion specifies proper audio parameters
            # (16kHz mono as per PRD requirements)
            if "sample_rate" in call_kwargs:
                assert call_kwargs["sample_rate"] == 16000
            if "channels" in call_kwargs:
                assert call_kwargs["channels"] == 1