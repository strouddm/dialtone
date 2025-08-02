"""Tests for audio converter service."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.services.audio_converter import AudioConverter, audio_converter


class TestAudioConverter:
    """Test cases for AudioConverter."""

    def test_initialization(self):
        """Test converter initialization."""
        converter = AudioConverter()
        assert converter.target_sample_rate == 16000
        assert converter.target_channels == 1
        assert converter.target_format == "wav"

    @patch("app.services.audio_converter.ffmpeg.probe")
    @patch("app.services.audio_converter.ffmpeg.input")
    async def test_convert_to_whisper_format_success(self, mock_input, mock_probe):
        """Test successful audio conversion."""
        # Mock probe response
        mock_probe.return_value = {
            "format": {"duration": "10.5"},
            "streams": [{"codec_type": "audio", "codec_name": "mp3"}],
        }

        # Mock ffmpeg chain
        mock_input_obj = Mock()
        mock_output_obj = Mock()
        mock_run_obj = Mock()

        mock_input.return_value = mock_input_obj
        mock_input_obj.output.return_value = mock_output_obj
        mock_output_obj.overwrite_output.return_value = mock_run_obj
        mock_run_obj.run.return_value = None

        # Mock file system
        input_path = Path("/test/input.mp3")
        output_dir = Path("/test/output")
        expected_output = output_dir / "converted_input.wav"

        with (
            patch.object(expected_output, "exists", return_value=True),
            patch.object(expected_output, "stat") as mock_stat,
        ):
            mock_stat.return_value.st_size = 12345

            converter = AudioConverter()
            result_path, duration = await converter.convert_to_whisper_format(
                input_path, output_dir
            )

            assert result_path == expected_output
            assert duration == 10.5

            # Verify ffmpeg calls
            mock_probe.assert_called_once_with(str(input_path))
            mock_input.assert_called_once_with(str(input_path))
            mock_input_obj.output.assert_called_once_with(
                str(expected_output),
                acodec="pcm_s16le",
                ac=1,
                ar=16000,
                format="wav",
            )

    @patch("app.services.audio_converter.ffmpeg.probe")
    async def test_convert_no_audio_stream(self, mock_probe):
        """Test conversion when no audio stream is found."""
        mock_probe.return_value = {
            "format": {"duration": "10.5"},
            "streams": [{"codec_type": "video"}],  # No audio stream
        }

        converter = AudioConverter()

        with pytest.raises(ValueError, match="No audio stream found"):
            await converter.convert_to_whisper_format(
                Path("/test/input.mp4"), Path("/test/output")
            )

    @patch("app.services.audio_converter.ffmpeg.probe")
    @patch("app.services.audio_converter.ffmpeg.input")
    async def test_convert_ffmpeg_error(self, mock_input, mock_probe):
        """Test handling of ffmpeg errors."""
        mock_probe.return_value = {
            "format": {"duration": "10.5"},
            "streams": [{"codec_type": "audio"}],
        }

        # Mock ffmpeg error
        from ffmpeg import Error

        mock_error = Error("ffmpeg", "", b"Conversion failed")

        mock_input_obj = Mock()
        mock_output_obj = Mock()
        mock_run_obj = Mock()

        mock_input.return_value = mock_input_obj
        mock_input_obj.output.return_value = mock_output_obj
        mock_output_obj.overwrite_output.return_value = mock_run_obj
        mock_run_obj.run.side_effect = mock_error

        converter = AudioConverter()

        with pytest.raises(HTTPException) as exc_info:
            await converter.convert_to_whisper_format(
                Path("/test/input.mp3"), Path("/test/output")
            )

        assert exc_info.value.status_code == 400
        assert "CONVERSION_ERROR" in str(exc_info.value.detail)

    @patch("app.services.audio_converter.ffmpeg.probe")
    @patch("app.services.audio_converter.ffmpeg.input")
    async def test_convert_output_not_created(self, mock_input, mock_probe):
        """Test when conversion completes but output file doesn't exist."""
        mock_probe.return_value = {
            "format": {"duration": "10.5"},
            "streams": [{"codec_type": "audio"}],
        }

        # Mock successful ffmpeg run
        mock_input_obj = Mock()
        mock_output_obj = Mock()
        mock_run_obj = Mock()

        mock_input.return_value = mock_input_obj
        mock_input_obj.output.return_value = mock_output_obj
        mock_output_obj.overwrite_output.return_value = mock_run_obj
        mock_run_obj.run.return_value = None

        # Mock output file doesn't exist
        output_path = Path("/test/output/converted_input.wav")
        with patch.object(output_path, "exists", return_value=False):
            converter = AudioConverter()

            with pytest.raises(RuntimeError, match="output file not found"):
                await converter.convert_to_whisper_format(
                    Path("/test/input.mp3"), Path("/test/output")
                )

    @patch("app.services.audio_converter.ffmpeg.probe")
    def test_is_conversion_needed_wav_correct_format(self, mock_probe):
        """Test conversion not needed for correct WAV format."""
        mock_probe.return_value = {
            "format": {"format_name": "wav"},
            "streams": [
                {
                    "codec_type": "audio",
                    "sample_rate": "16000",
                    "channels": "1",
                }
            ],
        }

        converter = AudioConverter()
        result = converter.is_conversion_needed(Path("/test/correct.wav"))

        assert result is False

    @patch("app.services.audio_converter.ffmpeg.probe")
    def test_is_conversion_needed_different_format(self, mock_probe):
        """Test conversion needed for different format."""
        mock_probe.return_value = {
            "format": {"format_name": "mp3"},
            "streams": [
                {
                    "codec_type": "audio",
                    "sample_rate": "44100",
                    "channels": "2",
                }
            ],
        }

        converter = AudioConverter()
        result = converter.is_conversion_needed(Path("/test/file.mp3"))

        assert result is True

    @patch("app.services.audio_converter.ffmpeg.probe")
    def test_is_conversion_needed_wrong_sample_rate(self, mock_probe):
        """Test conversion needed for wrong sample rate."""
        mock_probe.return_value = {
            "format": {"format_name": "wav"},
            "streams": [
                {
                    "codec_type": "audio",
                    "sample_rate": "44100",  # Wrong sample rate
                    "channels": "1",
                }
            ],
        }

        converter = AudioConverter()
        result = converter.is_conversion_needed(Path("/test/file.wav"))

        assert result is True

    @patch("app.services.audio_converter.ffmpeg.probe")
    def test_is_conversion_needed_probe_error(self, mock_probe):
        """Test conversion needed when probe fails."""
        mock_probe.side_effect = Exception("Probe failed")

        converter = AudioConverter()
        result = converter.is_conversion_needed(Path("/test/file.wav"))

        assert result is True  # Assume conversion needed on error

    @patch("app.services.audio_converter.ffmpeg.probe")
    async def test_get_audio_info_success(self, mock_probe):
        """Test successful audio info retrieval."""
        mock_probe.return_value = {
            "format": {
                "duration": "10.5",
                "size": "1024000",
                "format_name": "mp3",
            },
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": "mp3",
                    "sample_rate": "44100",
                    "channels": "2",
                    "bit_rate": "128000",
                }
            ],
        }

        converter = AudioConverter()
        info = await converter.get_audio_info(Path("/test/file.mp3"))

        expected_info = {
            "duration": 10.5,
            "size": 1024000,
            "format": "mp3",
            "codec": "mp3",
            "sample_rate": 44100,
            "channels": 2,
            "bit_rate": 128000,
        }

        assert info == expected_info

    @patch("app.services.audio_converter.ffmpeg.probe")
    async def test_get_audio_info_no_audio_stream(self, mock_probe):
        """Test audio info when no audio stream found."""
        mock_probe.return_value = {
            "format": {"duration": "10.5"},
            "streams": [{"codec_type": "video"}],  # No audio stream
        }

        converter = AudioConverter()

        with pytest.raises(HTTPException) as exc_info:
            await converter.get_audio_info(Path("/test/file.mp4"))

        assert exc_info.value.status_code == 400
        assert "INVALID_AUDIO" in str(exc_info.value.detail)

    @patch("app.services.audio_converter.ffmpeg.probe")
    async def test_get_audio_info_probe_error(self, mock_probe):
        """Test audio info when probe fails."""
        mock_probe.side_effect = Exception("Cannot probe file")

        converter = AudioConverter()

        with pytest.raises(HTTPException) as exc_info:
            await converter.get_audio_info(Path("/test/file.mp3"))

        assert exc_info.value.status_code == 400
        assert "INVALID_AUDIO" in str(exc_info.value.detail)

    def test_global_instance(self):
        """Test global audio_converter instance."""
        assert isinstance(audio_converter, AudioConverter)
        assert audio_converter.target_sample_rate == 16000
