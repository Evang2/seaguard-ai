from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Validated configuration for the SeaGuard backend."""

    app_name: str = "SeaGuard AI API"
    app_env: Literal["development", "test", "production"] = "development"
    app_debug: bool = False

    database_url: str

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Load and cache the application configuration."""

    return Settings()