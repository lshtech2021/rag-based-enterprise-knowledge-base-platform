from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    auth_mode: str = "dev_bypass"
    jwt_secret: str = "dev-only-change-me"


def get_settings() -> Settings:
    return Settings()
