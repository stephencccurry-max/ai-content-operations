from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://app:app@localhost:5432/ai_content_ops"
    internal_api_token: str = "dev-internal-token"
    export_dir: Path = Path("data/exports")
    app_version: str = "0.1.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
