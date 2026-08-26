"""OpenAI-compatible embeddings adapter for document vectors."""

from __future__ import annotations

import os

import httpx
from openai import AsyncOpenAI

DEFAULT_MODEL = "text-embedding-3-small"
DEFAULT_DIMENSIONS = 1536
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_BATCH_SIZE = 64


def resolve_openai_base_url(base_url: str | None = None) -> str:
    resolved = (base_url or os.environ.get("OPENAI_BASE_URL", "")).strip() or DEFAULT_BASE_URL
    return resolved.rstrip("/")


class OpenAIEmbedder:
    """Calls OpenAI-compatible ``/v1/embeddings`` via the official SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str = DEFAULT_MODEL,
        dimensions: int = DEFAULT_DIMENSIONS,
        base_url: str | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        client: AsyncOpenAI | None = None,
        http_client: httpx.AsyncClient | None = None,
        api_key_env: str = "OPENAI_API_KEY",
    ) -> None:
        self._model = model
        self._dimensions = dimensions
        self._base_url = resolve_openai_base_url(base_url)
        self._batch_size = max(1, batch_size)
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            key = (api_key if api_key is not None else os.environ.get(api_key_env, "")).strip()
            if not key:
                raise ValueError(f"{api_key_env} is required for OpenAIEmbedder")
            self._client = AsyncOpenAI(
                api_key=key,
                base_url=self._base_url,
                http_client=http_client,
                timeout=60.0,
            )
            self._owns_client = http_client is None

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def batch_size(self) -> int:
        return self._batch_size

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.close()

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            response = await self._client.embeddings.create(
                model=self._model,
                input=batch,
                dimensions=self._dimensions,
            )
            ordered = sorted(response.data, key=lambda row: row.index)
            out.extend(list(row.embedding) for row in ordered)
        return out


def require_openai_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "OPENAI_API_KEY is required for live ingestion embeddings. "
            "Set it in the environment or .env."
        )
    return key
