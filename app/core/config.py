from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # General App Settings
    APP_NAME: str = "jellyfin-ai-sidecar"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    # Jellyfin Connection
    JELLYFIN_SERVER_URL: Optional[str] = None
    JELLYFIN_API_KEY: Optional[str] = None
    JELLYFIN_WEBHOOK_SECRET: Optional[str] = None

    # Database Configuration (PostgreSQL + pgvector)
    POSTGRES_USER: str = "jellyfin_user"
    POSTGRES_PASSWORD: str = "jellyfin_pass"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "jellyfin_ai"
    DATABASE_URL: Optional[str] = None

    # Embedding Settings
    EMBEDDING_DIMENSION: int = 768

    # Chunker Settings
    CHUNK_SIZE_SECONDS: int = 30
    CHUNK_OVERLAP_SECONDS: int = 5

    # FFmpeg Configuration
    FFMPEG_PATH: str = "ffmpeg"
    FFPROBE_PATH: str = "ffprobe"

    # LLM & RAG Configuration
    LLM_PROVIDER: str = "openai"  # openai, gemini, anthropic, groq, ollama, custom, none
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: Optional[str] = None
    LLM_BASE_URL: Optional[str] = None
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 1024
    RAG_TOP_K: int = 5

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

