"""Centralised application configuration.

All runtime configuration is sourced from environment variables (or a local
``.env`` file in development) via Pydantic Settings. Nothing here should be
hardcoded for production secrets.
"""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Environment ---
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: str = "INFO"

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://nova_user:changeme@localhost:5432/nova_db"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379"

    # --- Rate limiter storage backend ---
    # "memory://" for local dev/tests (per-process, fine for a single
    # worker). Set to REDIS_URL in production so limits are shared across
    # the multiple Gunicorn worker processes (see Dockerfile --workers 2).
    RATE_LIMIT_STORAGE_URI: str = "memory://"

    # --- JWT ---
    JWT_SECRET_KEY: str = "insecure-dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- Encryption (AES-256 / Fernet for face embeddings & PII) ---
    EMBEDDING_ENCRYPTION_KEY: str = "0" * 64  # 32-byte hex, override in production

    # --- Scene description (VLM) ---
    USE_LOCAL_VLM: bool = True
    OPENAI_API_KEY: str = ""
    VLM_MODEL_NAME: str = "Salesforce/blip2-opt-2.7b"

    # --- Rate limiting ---
    RATE_LIMIT_PER_MINUTE: int = 60

    # --- Model registry ---
    MODEL_STORAGE_PATH: str = "./models"

    # --- CORS ---
    CORS_ORIGINS: str = "*"

    # --- Face matching ---
    FACE_MATCH_THRESHOLD: float = 0.75
    ON_DEVICE_GALLERY_LIMIT: int = 20

    @property
    def async_database_url(self) -> str:
        """DATABASE_URL normalised for the async driver.

        Render (and Heroku-style providers) inject ``postgres://`` or
        ``postgresql://`` URLs; SQLAlchemy's asyncpg dialect needs the
        ``postgresql+asyncpg://`` scheme.
        """
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        # asyncpg's SQLAlchemy dialect rejects libpq's sslmode param; it
        # accepts ssl=require instead.
        return url.replace("?sslmode=require", "?ssl=require").replace(
            "&sslmode=require", "&ssl=require")

    @property
    def cors_origin_list(self) -> list[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
