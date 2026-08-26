"""OpenAI embeddings adapter for query vectors."""

from __future__ import annotations

import os

import httpx

DEFAULT_MODEL = "text-embedding-3-small"
DEFAULT_DIMENSIONS = 1536
DEFAULT_BASE_URL = "https://api.openai.com/v1"


def resolve_openai_base_url(base_url: str | None = None) -> str:
    resolved = (base_url or os.environ.get("OPENAI_BASE_URL", "")).strip() or DEFAULT_BASE_URL
    return resolved.rstrip("/")


class OpenAIQueryEmbedder:
    """Calls OpenAI ``/v1/embeddings`` for a single query string."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str = DEFAULT_MODEL,
        dimensions: int = DEFAULT_DIMENSIONS,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        key = (api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")).strip()
        if not key:
            raise ValueError("OPENAI_API_KEY is required for OpenAIQueryEmbedder")
        self._api_key = key
        self._model = model
        self._dimensions = dimensions
        self._base_url = resolve_openai_base_url(base_url)
        self._client = client
        self._owns_client = client is None

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def model(self) -> str:
        return self._model

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def embed_query(self, text: str) -> list[float]:
        client = await self._ensure_client()
        response = await client.post(
            f"{self._base_url}/embeddings",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "input": text,
                "dimensions": self._dimensions,
            },
        )
        response.raise_for_status()
        payload = response.json()
        return list(payload["data"][0]["embedding"])

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client
