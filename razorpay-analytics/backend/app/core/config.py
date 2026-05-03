"""
Configuration settings for the Razorpay Analytics SaaS.
All settings are loaded from environment variables.
"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    APP_NAME: str = "Razorpay Analytics SaaS"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/razorpay_analytics"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 3600  # 1 hour

    # Security
    SECRET_KEY: str = "change-this-in-production-min-32-chars!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    FERNET_KEY: Optional[str] = None  # For encrypting Razorpay tokens

    # Razorpay OAuth
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/razorpay/callback"
    RAZORPAY_BASE_URL: str = "https://api.razorpay.com/v1"

    # LLM (Anthropic Claude)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    LLM_TEMPERATURE: float = 0.0  # Deterministic for SQL generation
    LLM_MAX_TOKENS: int = 4096

    # Embeddings (OpenAI compatible)
    EMBEDDINGS_MODEL: str = "text-embedding-3-large"
    EMBEDDINGS_DIMENSION: int = 1536

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Rate Limiting
    FREE_TIER_QUERIES_PER_DAY: int = 20

    # Logging
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
