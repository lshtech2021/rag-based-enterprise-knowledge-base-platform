from __future__ import annotations

import httpx
import pytest
from kb_ingestion.infrastructure.embeddings.openai_embedder import OpenAIEmbedder


def _embedding_response(rows: list[tuple[int, list[float]]]) -> dict:
    return {
        "object": "list",
        "data": [
            {"object": "embedding", "index": index, "embedding": vector}
            for index, vector in rows
        ],
        "model": "text-embedding-3-small",
        "usage": {"prompt_tokens": len(rows), "total_tokens": len(rows)},
    }


@pytest.mark.asyncio
async def test_openai_embedder_batches_and_orders() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/embeddings")
        return httpx.Response(
            200,
            json=_embedding_response([(1, [0.0, 1.0]), (0, [1.0, 0.0])]),
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    embedder = OpenAIEmbedder(
        api_key="test-key",
        dimensions=2,
        http_client=http_client,
    )
    vectors = await embedder.embed_documents(["a", "b"])
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]
    assert embedder.dimensions == 2
    assert embedder.model == "text-embedding-3-small"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_openai_embedder_uses_custom_base_url() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json=_embedding_response([(0, [1.0, 0.0])]))

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    embedder = OpenAIEmbedder(
        api_key="test-key",
        dimensions=2,
        base_url="https://llm.example.com/v1/",
        http_client=http_client,
    )
    await embedder.embed_documents(["a"])
    assert seen
    assert seen[0].startswith("https://llm.example.com/v1/embeddings")
    await http_client.aclose()


def test_openai_embedder_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIEmbedder()


def test_resolve_openai_base_url_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from kb_ingestion.infrastructure.embeddings.openai_embedder import (
        resolve_openai_base_url,
    )

    monkeypatch.setenv("OPENAI_BASE_URL", "https://proxy.example/v1/")
    assert resolve_openai_base_url() == "https://proxy.example/v1"


def test_build_openai_embedder_passes_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from kb_ingestion.infrastructure.wiring import build_openai_embedder

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    embedder = build_openai_embedder(
        base_url="https://gateway.local/v1",
        model="custom-embed",
    )
    assert embedder.model == "custom-embed"
    assert embedder.base_url == "https://gateway.local/v1"
