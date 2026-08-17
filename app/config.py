from __future__ import annotations

import functools

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: str
    # Both deprecated by Groq 2026-08-16 (console.groq.com/docs/deprecations);
    # replaced with their documented same-tier successors.
    llm_model: str = "openai/gpt-oss-120b"
    llm_fallback_model: str = "openai/gpt-oss-20b"

    embedding_model: str = "all-MiniLM-L6-v2"
    min_train_per_category: int = 30
    min_anomaly_samples: int = 50
    min_forecast_months: int = 3
    models_dir: str = "models"
    # Zero-shot confidence below this score triggers LLM fallback in categorizer
    categorizer_fallback_threshold: float = 0.30

    # Phase 3a — production config
    database_url: str = "sqlite:///./expense_tracker.db"
    supabase_jwt_secret: str = ""
    supabase_url: str = ""
    admin_enabled: bool = False
    run_migrations_on_startup: bool = False
    cors_allowed_origins: str = ""  # comma-separated list; empty means default dev origins only


@functools.lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()  # type: ignore[call-arg]  # groq_api_key populated from env, mypy can't see that
