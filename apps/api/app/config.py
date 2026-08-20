from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://app:app@localhost:5432/ai_content_ops"
    internal_api_token: str
    export_dir: Path = Path("data/exports")
    app_version: str = "0.1.0"
    llm_provider: str = "mock"
    search_provider: str = "mock"
    zhipu_api_key: str | None = None
    zhipu_base_url: str = "https://open.bigmodel.cn/api/coding/paas/v4"
    zhipu_model: str = "glm-5.3"
    tavily_api_key: str | None = None
    provider_timeout_seconds: float = 45.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
