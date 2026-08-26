"""OpenAI-compatible embeddings adapter for query vectors."""

from __future__ import annotations

import os

import httpx
from openai import AsyncOpenAI

DEFAULT_MODEL = "text-embedding-3-small"
DEFAULT_DIMENSIONS = 1536
DEFAULT_BASE_URL = "https://api.openai.com/v1"


def resolve_openai_base_url(base_url: str | None = None) -> str:
    resolved = (base_url or os.environ.get("OPENAI_BASE_URL", "")).strip() or DEFAULT_BASE_URL
    return resolved.rstrip("/")


class OpenAIQueryEmbedder:
    """Calls OpenAI-compatible ``/v1/embeddings`` via the official SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str = DEFAULT_MODEL,
        dimensions: int = DEFAULT_DIMENSIONS,
        base_url: str | None = None,
        client: AsyncOpenAI | None = None,
        http_client: httpx.AsyncClient | None = None,
        api_key_env: str = "OPENAI_API_KEY",
    ) -> None:
        self._model = model
        self._dimensions = dimensions
        self._base_url = resolve_openai_base_url(base_url)
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            key = (api_key if api_key is not None else os.environ.get(api_key_env, "")).strip()
            if not key:
                raise ValueError(f"{api_key_env} is required for OpenAIQueryEmbedder")
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

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.close()

    async def embed_query(self, text: str) -> list[float]:
        response = await self._client.embeddings.create(
            model=self._model,
            input=text,
            dimensions=self._dimensions,
        )
        return list(response.data[0].embedding)
