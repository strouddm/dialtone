"""Audio converter service for format conversion using ffmpeg."""

import logging
from pathlib import Path
from typing import Tuple

import ffmpeg
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class AudioConverter:
    """Service for converting audio files to Whisper-compatible format."""

    def __init__(self):
        """Initialize audio converter."""
        self.target_sample_rate = 16000  # Optimal for Whisper
        self.target_channels = 1  # Mono
        self.target_format = "wav"  # Whisper-compatible format

    async def convert_to_whisper_format(
        self, input_path: Path, output_dir: Path
    ) -> Tuple[Path, float]:
        """Convert audio file to Whisper-compatible format.

        Args:
            input_path: Path to input audio file
            output_dir: Directory to store converted file

        Returns:
            Tuple of (converted_file_path, duration_seconds)
        """
        try:
            # Create unique output filename
            converted_filename = f"converted_{input_path.stem}.wav"
            output_path = output_dir / converted_filename

            logger.info(
                "Starting audio conversion",
                extra={
                    "input_path": str(input_path),
                    "output_path": str(output_path),
                    "target_sample_rate": self.target_sample_rate,
                    "target_channels": self.target_channels,
                },
            )

            # Get input file info
            probe = ffmpeg.probe(str(input_path))
            duration = float(probe["format"]["duration"])

            # Get audio stream info
            audio_streams = [
                stream for stream in probe["streams"] if stream["codec_type"] == "audio"
            ]

            if not audio_streams:
                raise ValueError("No audio stream found in file")

            # Convert audio using ffmpeg
            (
                ffmpeg.input(str(input_path))
                .output(
                    str(output_path),
                    acodec="pcm_s16le",  # 16-bit PCM
                    ac=self.target_channels,  # Mono
                    ar=self.target_sample_rate,  # 16kHz sample rate
                    format="wav",
                )
                .overwrite_output()  # Overwrite if exists
                .run(capture_stdout=True, capture_stderr=True, check=True)
            )

            # Verify output file was created
            if not output_path.exists():
                raise RuntimeError("Conversion completed but output file not found")

            logger.info(
                "Audio conversion completed",
                extra={
                    "input_path": str(input_path),
                    "output_path": str(output_path),
                    "duration_seconds": duration,
                    "output_size": output_path.stat().st_size,
                },
            )

            return output_path, duration

        except ffmpeg.Error as e:
            error_msg = (
                f"FFmpeg conversion failed: {e.stderr.decode() if e.stderr else str(e)}"
            )
            logger.error(
                "Audio conversion failed",
                extra={
                    "input_path": str(input_path),
                    "error": error_msg,
                },
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Audio conversion failed",
                    "error_code": "CONVERSION_ERROR",
                    "details": error_msg,
                },
            ) from e

        except Exception as e:
            error_msg = f"Audio conversion error: {str(e)}"
            logger.error(
                "Audio conversion error",
                extra={
                    "input_path": str(input_path),
                    "error": error_msg,
                },
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Audio processing failed",
                    "error_code": "PROCESSING_ERROR",
                },
            ) from e

    def is_conversion_needed(self, file_path: Path) -> bool:
        """Check if file needs conversion for Whisper compatibility."""
        try:
            probe = ffmpeg.probe(str(file_path))

            # Check if it's already a WAV file with correct specs
            format_name = probe["format"]["format_name"]
            if "wav" not in format_name.lower():
                return True

            # Check audio stream properties
            audio_streams = [
                stream for stream in probe["streams"] if stream["codec_type"] == "audio"
            ]

            if not audio_streams:
                return True

            stream = audio_streams[0]
            sample_rate = int(stream.get("sample_rate", 0))
            channels = int(stream.get("channels", 0))

            # Needs conversion if not 16kHz mono WAV
            needs_conversion: bool = (
                sample_rate != self.target_sample_rate
                or channels != self.target_channels
            )
            return needs_conversion

        except Exception as e:
            logger.warning(
                "Could not probe audio file, assuming conversion needed",
                extra={"file_path": str(file_path), "error": str(e)},
            )
            return True

    async def get_audio_info(self, file_path: Path) -> dict:
        """Get audio file information."""
        try:
            probe = ffmpeg.probe(str(file_path))

            format_info = probe["format"]
            audio_streams = [
                stream for stream in probe["streams"] if stream["codec_type"] == "audio"
            ]

            if not audio_streams:
                raise ValueError("No audio stream found")

            stream = audio_streams[0]

            return {
                "duration": float(format_info.get("duration", 0)),
                "size": int(format_info.get("size", 0)),
                "format": format_info.get("format_name", "unknown"),
                "codec": stream.get("codec_name", "unknown"),
                "sample_rate": int(stream.get("sample_rate", 0)),
                "channels": int(stream.get("channels", 0)),
                "bit_rate": (
                    int(stream.get("bit_rate", 0)) if stream.get("bit_rate") else None
                ),
            }

        except Exception as e:
            logger.error(
                "Failed to get audio info",
                extra={"file_path": str(file_path), "error": str(e)},
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Cannot read audio file",
                    "error_code": "INVALID_AUDIO",
                },
            ) from e


# Global service instance
audio_converter = AudioConverter()
