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
    llm_model: str = "llama-3.3-70b-versatile"
    llm_fallback_model: str = "llama-3.1-8b-instant"

    embedding_model: str = "all-MiniLM-L6-v2"
    min_train_per_category: int = 30
    min_anomaly_samples: int = 50
    min_forecast_months: int = 3
    models_dir: str = "models"
    # Zero-shot confidence below this score triggers LLM fallback in categorizer
    categorizer_fallback_threshold: float = 0.30


@functools.lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()  # type: ignore[call-arg]  # groq_api_key populated from env, mypy can't see that
