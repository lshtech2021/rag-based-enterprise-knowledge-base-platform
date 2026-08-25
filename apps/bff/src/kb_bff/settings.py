from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    auth_mode: str = "dev_bypass"
    jwt_secret: str = "dev-only-change-me"
    sec_user_agent: str = ""
    ingest_data_dir: str = "data/ingestion"
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"


def get_settings() -> Settings:
    return Settings()
