"""Application settings using Pydantic."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = Field(default="Dialtone", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    # Paths
    obsidian_vault_path: Path = Field(
        default=Path("/vault"), description="Path to Obsidian vault"
    )
    upload_dir: Path = Field(
        default=Path("/tmp/voice-notes/uploads"),
        description="Directory for temporary upload storage",
    )

    # Processing limits
    max_upload_size: int = Field(
        default=52428800,  # 50MB
        description="Maximum upload size in bytes",
        ge=1048576,  # Min 1MB
        le=104857600,  # Max 100MB
    )
    processing_timeout: int = Field(
        default=35, description="Processing timeout in seconds", ge=10, le=300
    )
    max_concurrent_requests: int = Field(
        default=3, description="Maximum concurrent processing requests", ge=1, le=10
    )

    # Audio processing
    supported_audio_types: list[str] = Field(
        default=["audio/webm", "audio/mp4", "audio/mpeg"],
        description="Supported audio MIME types",
    )
    upload_cleanup_hours: int = Field(
        default=1,
        description="Hours to keep uploaded files before cleanup",
        ge=1,
        le=24,
    )

    # Whisper transcription
    whisper_model_size: str = Field(
        default="base",
        description="Whisper model size (tiny, base, small, medium, large)",
    )
    whisper_device: str = Field(
        default="cpu",
        description="Device for Whisper processing (cpu, cuda)",
    )
    whisper_compute_type: str = Field(
        default="int8",
        description="Compute type for Whisper (int8, int16, float16, float32)",
    )
    max_concurrent_transcriptions: int = Field(
        default=2,
        description="Maximum concurrent transcriptions",
        ge=1,
        le=5,
    )
    transcription_timeout: int = Field(
        default=300,
        description="Transcription timeout in seconds",
        ge=60,
        le=900,
    )

    # Server
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port", ge=1, le=65535)
    workers: int = Field(default=1, description="Number of workers", ge=1, le=8)
    reload: bool = Field(default=False, description="Enable auto-reload")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level. Must be one of: {valid_levels}")
        return v_upper

    @field_validator("obsidian_vault_path")
    @classmethod
    def validate_vault_path(cls, v: Path) -> Path:
        """Ensure vault path exists or can be created."""
        if not v.exists():
            try:
                v.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise ValueError(f"Cannot create vault path: {e}")
        return v

    @field_validator("upload_dir")
    @classmethod
    def validate_upload_dir(cls, v: Path) -> Path:
        """Ensure upload directory exists or can be created."""
        if not v.exists():
            try:
                v.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise ValueError(f"Cannot create upload directory: {e}")
        return v


# Global settings instance
settings = Settings()
