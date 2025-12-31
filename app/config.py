"""
Application configuration using Pydantic Settings.
Loads from environment variables with .env file support.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ===================
    # SUPABASE
    # ===================
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_KEY: Optional[str] = None

    # ===================
    # LLMs
    # ===================
    OPENAI_API_KEY: str
    ANTHROPIC_API_KEY: Optional[str] = None

    # ===================
    # WHATSAPP (GUPSHUP)
    # ===================
    GUPSHUP_API_KEY: Optional[str] = None
    GUPSHUP_NAMESPACE: Optional[str] = None
    WHATSAPP_PHONE_NUMBER: Optional[str] = None
    WHATSAPP_APP_NAME: str = "TigerMomAI"

    # ===================
    # WEBHOOK
    # ===================
    WEBHOOK_VERIFY_TOKEN: str = "tiger-mom-verify-token"

    # ===================
    # ADMIN
    # ===================
    ADMIN_API_KEY: str = "admin-secret-key"

    # ===================
    # DATABASE
    # ===================
    DATABASE_URL: Optional[str] = None

    # ===================
    # APP CONFIG
    # ===================
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    DEFAULT_NUDGE_TIME: str = "18:00"

    # ===================
    # EMBEDDING CONFIG
    # ===================
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
