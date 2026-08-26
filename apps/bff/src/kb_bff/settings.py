from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    auth_mode: str = "dev_bypass"
    jwt_secret: str = "dev-only-change-me"
    sec_user_agent: str = ""
    ingest_data_dir: str = "data/ingestion"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"
    # Embedding provider: openai | dashscope (alias: qwen)
    embedding_provider: str = "openai"
    embedding_dimensions: int = 1536
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_embedding_model: str = "qwen3.7-text-embedding"
    kb_data_plane: str = "local"
    database_url: str = "postgresql://kb:kb@localhost:5432/knowledge_base"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "kb-filings"
    opensearch_url: str = "http://localhost:9200"
    opensearch_username: str = "admin"
    opensearch_password: str = "admin"
    log_level: str = "INFO"


def get_settings() -> Settings:
    return Settings()
