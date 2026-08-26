"""DashScope / Qwen embedding defaults (OpenAI-compatible mode)."""

from __future__ import annotations

import os

DEFAULT_MODEL = "qwen3.7-text-embedding"
DEFAULT_DIMENSIONS = 1536
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
BATCH_SIZE = 20  # qwen3.7-text-embedding max texts per request


def resolve_dashscope_base_url(base_url: str | None = None) -> str:
    resolved = (base_url or os.environ.get("DASHSCOPE_BASE_URL", "")).strip() or DEFAULT_BASE_URL
    return resolved.rstrip("/")


def require_dashscope_api_key(api_key: str | None = None) -> str:
    key = (api_key if api_key is not None else os.environ.get("DASHSCOPE_API_KEY", "")).strip()
    if not key:
        raise ValueError(
            "DASHSCOPE_API_KEY is required for DashScope/Qwen embeddings. "
            "Set it in the environment or .env."
        )
    return key
