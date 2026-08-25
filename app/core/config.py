from typing import Optional
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # General App Settings
    APP_NAME: str = "jellyfin-ai-sidecar"
    DEBUG: bool = Field(default=False, validation_alias=AliasChoices("AI_SIDECAR_DEBUG", "DEBUG"))
    API_V1_STR: str = "/api/v1"

    # Jellyfin Connection
    JELLYFIN_SERVER_URL: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("AI_SIDECAR_JELLYFIN_SERVER_URL", "JELLYFIN_SERVER_URL")
    )
    JELLYFIN_API_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("AI_SIDECAR_JELLYFIN_API_KEY", "JELLYFIN_API_KEY")
    )
    JELLYFIN_WEBHOOK_SECRET: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("AI_SIDECAR_JELLYFIN_WEBHOOK_SECRET", "JELLYFIN_WEBHOOK_SECRET")
    )

    # Database Configuration (PostgreSQL + pgvector)
    POSTGRES_USER: str = Field(
        default="jellyfin_user",
        validation_alias=AliasChoices("AI_SIDECAR_DB_USER", "AI_POSTGRES_USER", "POSTGRES_USER")
    )
    POSTGRES_PASSWORD: str = Field(
        default="jellyfin_pass",
        validation_alias=AliasChoices("AI_SIDECAR_DB_PASSWORD", "AI_POSTGRES_PASSWORD", "POSTGRES_PASSWORD")
    )
    POSTGRES_HOST: str = Field(
        default="db",
        validation_alias=AliasChoices("AI_SIDECAR_DB_HOST", "POSTGRES_HOST")
    )
    POSTGRES_PORT: int = Field(
        default=5432,
        validation_alias=AliasChoices("AI_SIDECAR_DB_PORT", "POSTGRES_PORT")
    )
    POSTGRES_DB: str = Field(
        default="jellyfin_ai",
        validation_alias=AliasChoices("AI_SIDECAR_DB_NAME", "AI_POSTGRES_DB", "POSTGRES_DB")
    )
    DATABASE_URL: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("AI_SIDECAR_DATABASE_URL", "DATABASE_URL")
    )

    # Embedding Settings
    EMBEDDING_DIMENSION: int = Field(
        default=768,
        validation_alias=AliasChoices("AI_SIDECAR_EMBEDDING_DIMENSION", "EMBEDDING_DIMENSION")
    )

    # Chunker Settings
    CHUNK_SIZE_SECONDS: int = Field(
        default=30,
        validation_alias=AliasChoices("AI_SIDECAR_CHUNK_SIZE_SECONDS", "CHUNK_SIZE_SECONDS")
    )
    CHUNK_OVERLAP_SECONDS: int = Field(
        default=5,
        validation_alias=AliasChoices("AI_SIDECAR_CHUNK_OVERLAP_SECONDS", "CHUNK_OVERLAP_SECONDS")
    )

    # FFmpeg Configuration
    FFMPEG_PATH: str = Field(
        default="ffmpeg",
        validation_alias=AliasChoices("AI_SIDECAR_FFMPEG_PATH", "FFMPEG_PATH")
    )
    FFPROBE_PATH: str = Field(
        default="ffprobe",
        validation_alias=AliasChoices("AI_SIDECAR_FFPROBE_PATH", "FFPROBE_PATH")
    )

    # LLM & RAG Configuration
    LLM_PROVIDER: str = Field(
        default="openai",
        validation_alias=AliasChoices("AI_SIDECAR_LLM_PROVIDER", "LLM_PROVIDER")
    )
    LLM_API_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("AI_SIDECAR_LLM_API_KEY", "LLM_API_KEY")
    )
    LLM_MODEL: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("AI_SIDECAR_LLM_MODEL", "LLM_MODEL")
    )
    LLM_BASE_URL: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("AI_SIDECAR_LLM_BASE_URL", "LLM_BASE_URL")
    )
    LLM_TEMPERATURE: float = Field(
        default=0.2,
        validation_alias=AliasChoices("AI_SIDECAR_LLM_TEMPERATURE", "LLM_TEMPERATURE")
    )
    LLM_MAX_TOKENS: int = Field(
        default=1024,
        validation_alias=AliasChoices("AI_SIDECAR_LLM_MAX_TOKENS", "LLM_MAX_TOKENS")
    )
    RAG_TOP_K: int = Field(
        default=15,
        validation_alias=AliasChoices("AI_SIDECAR_RAG_TOP_K", "RAG_TOP_K")
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def get_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()

