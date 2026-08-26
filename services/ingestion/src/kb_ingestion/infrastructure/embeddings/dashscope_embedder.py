"""Alibaba DashScope (Qwen) text embeddings for document vectors.

Mirrors ``dashscope.TextEmbedding.call`` over the DashScope HTTP API so we
stay dependency-light (httpx only) and testable with MockTransport.
"""

from __future__ import annotations

import os

import httpx

DEFAULT_MODEL = "qwen3.7-text-embedding"
# Match the existing Postgres ``vector(1536)`` column; Qwen supports 1536.
DEFAULT_DIMENSIONS = 1536
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_ENDPOINT = "/embeddings"
_BATCH_SIZE = 20  # qwen3.7-text-embedding max texts per request


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


class DashScopeEmbedder:
    """Calls DashScope TextEmbedding for document batches."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str = DEFAULT_MODEL,
        dimensions: int = DEFAULT_DIMENSIONS,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = require_dashscope_api_key(api_key)
        self._model = model
        self._dimensions = dimensions
        self._base_url = resolve_dashscope_base_url(base_url)
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
            out.extend(await self._embed_batch(client, batch, text_type="document"))
        return out

    async def _embed_batch(
        self, client: httpx.AsyncClient, texts: list[str], *, text_type: str
    ) -> list[list[float]]:
        response = await client.post(
            f"{self._base_url}{_ENDPOINT}",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "input": {"texts": texts},
                "parameters": {
                    "dimension": self._dimensions,
                    "text_type": text_type,
                },
            },
        )
        response.raise_for_status()
        payload = response.json()
        status_code = payload.get("status_code", response.status_code)
        if status_code != 200:
            raise RuntimeError(
                f"DashScope embedding failed: code={payload.get('code')} "
                f"message={payload.get('message')}"
            )
        items = payload.get("data", [])
        embeddings = [item.get("embedding") for item in items if "embedding" in item]
        if len(embeddings) != len(texts):
            raise RuntimeError(
                f"DashScope embedding returned {len(embeddings)} embeddings for "
                f"{len(texts)} texts"
            )
        ordered = sorted(embeddings, key=lambda row: int(row.get("text_index", 0)))
        return [list(row["embedding"]) for row in ordered]

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client
