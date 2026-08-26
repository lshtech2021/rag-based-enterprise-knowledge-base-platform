"""OpenAI embeddings adapter for document vectors."""

from __future__ import annotations

import os

import httpx

DEFAULT_MODEL = "text-embedding-3-small"
DEFAULT_DIMENSIONS = 1536
DEFAULT_BASE_URL = "https://api.openai.com/v1"
_BATCH_SIZE = 64


def resolve_openai_base_url(base_url: str | None = None) -> str:
    resolved = (base_url or os.environ.get("OPENAI_BASE_URL", "")).strip() or DEFAULT_BASE_URL
    return resolved.rstrip("/")


class OpenAIEmbedder:
    """Calls OpenAI ``/v1/embeddings`` via httpx."""

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
            raise ValueError("OPENAI_API_KEY is required for OpenAIEmbedder")
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

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = await self._ensure_client()
        out: list[list[float]] = []
        for start in range(0, len(texts), _BATCH_SIZE):
            batch = texts[start : start + _BATCH_SIZE]
            response = await client.post(
                f"{self._base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "input": batch,
                    "dimensions": self._dimensions,
                },
            )
            response.raise_for_status()
            payload = response.json()
            data = sorted(payload["data"], key=lambda row: row["index"])
            out.extend(row["embedding"] for row in data)
        return out

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client


def require_openai_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "OPENAI_API_KEY is required for live ingestion embeddings. "
            "Set it in the environment or .env."
        )
    return key
