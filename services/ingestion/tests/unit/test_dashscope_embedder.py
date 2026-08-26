from __future__ import annotations

import json

import httpx
import pytest
from kb_ingestion.infrastructure.embeddings.dashscope_config import (
    DEFAULT_BASE_URL,
    require_dashscope_api_key,
)
from kb_ingestion.infrastructure.embeddings.openai_embedder import OpenAIEmbedder
from kb_ingestion.infrastructure.wiring import build_dashscope_embedder
from kb_query.infrastructure.embeddings.openai_query_embedder import OpenAIQueryEmbedder


def _embedding_response(
    rows: list[tuple[int, list[float]]], *, model: str = "qwen3.7-text-embedding"
) -> dict:
    return {
        "object": "list",
        "data": [
            {"object": "embedding", "index": index, "embedding": vector}
            for index, vector in rows
        ],
        "model": model,
        "usage": {"prompt_tokens": len(rows), "total_tokens": len(rows)},
    }


@pytest.mark.asyncio
async def test_dashscope_embedder_via_openai_compatible_api() -> None:
    seen_bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/embeddings")
        body = json.loads(request.content)
        seen_bodies.append(body)
        assert body["model"] == "qwen3.7-text-embedding"
        assert body["input"] == ["a", "b"]
        assert body["dimensions"] == 2
        return httpx.Response(
            200,
            json=_embedding_response([(1, [0.0, 1.0]), (0, [1.0, 0.0])]),
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    embedder = OpenAIEmbedder(
        api_key="test-key",
        model="qwen3.7-text-embedding",
        dimensions=2,
        base_url=DEFAULT_BASE_URL,
        batch_size=20,
        http_client=http_client,
        api_key_env="DASHSCOPE_API_KEY",
    )
    vectors = await embedder.embed_documents(["a", "b"])
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]
    assert embedder.model == "qwen3.7-text-embedding"
    assert seen_bodies[0]["input"] == ["a", "b"]
    await http_client.aclose()


@pytest.mark.asyncio
async def test_dashscope_embedder_uses_custom_base_url() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json=_embedding_response([(0, [1.0, 0.0])]))

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    embedder = OpenAIEmbedder(
        api_key="test-key",
        model="qwen3.7-text-embedding",
        dimensions=2,
        base_url="https://dashscope.example.com/compatible-mode/v1/",
        batch_size=20,
        http_client=http_client,
        api_key_env="DASHSCOPE_API_KEY",
    )
    await embedder.embed_documents(["a"])
    assert seen
    assert seen[0].startswith(
        "https://dashscope.example.com/compatible-mode/v1/embeddings"
    )
    await http_client.aclose()


@pytest.mark.asyncio
async def test_dashscope_query_embedder_via_openai_compatible_api() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["input"] == "risk factors"
        assert body["model"] == "qwen3.7-text-embedding"
        return httpx.Response(200, json=_embedding_response([(0, [0.5, 0.5])]))

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    embedder = OpenAIQueryEmbedder(
        api_key="test-key",
        model="qwen3.7-text-embedding",
        dimensions=2,
        base_url=DEFAULT_BASE_URL,
        http_client=http_client,
        api_key_env="DASHSCOPE_API_KEY",
    )
    vector = await embedder.embed_query("risk factors")
    assert vector == [0.5, 0.5]
    assert embedder.model == "qwen3.7-text-embedding"
    await http_client.aclose()


def test_dashscope_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
        require_dashscope_api_key()


def test_resolve_embedding_provider_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    from kb_ingestion.infrastructure.wiring import resolve_embedding_provider

    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    assert resolve_embedding_provider("qwen") == "dashscope"
    assert resolve_embedding_provider("dashscope") == "dashscope"
    assert resolve_embedding_provider("openai") == "openai"
    with pytest.raises(ValueError, match="Unsupported EMBEDDING_PROVIDER"):
        resolve_embedding_provider("unknown")


def test_build_dashscope_embedder_passes_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.delenv("EMBEDDING_BATCH_SIZE", raising=False)
    embedder = build_dashscope_embedder(
        model="qwen3.7-text-embedding",
        base_url="https://dashscope.example.com/compatible-mode/v1",
        dimensions=1536,
    )
    assert isinstance(embedder, OpenAIEmbedder)
    assert embedder.model == "qwen3.7-text-embedding"
    assert embedder.dimensions == 1536
    assert embedder.base_url == "https://dashscope.example.com/compatible-mode/v1"
    assert embedder.batch_size == 20


def test_resolve_embedding_batch_size_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    from kb_ingestion.infrastructure.wiring import resolve_embedding_batch_size

    monkeypatch.delenv("EMBEDDING_BATCH_SIZE", raising=False)
    assert resolve_embedding_batch_size(provider="openai") == 64
    assert resolve_embedding_batch_size(provider="dashscope") == 20
    assert resolve_embedding_batch_size(10, provider="dashscope") == 10
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "15")
    assert resolve_embedding_batch_size(provider="openai") == 15


def test_build_openai_embedder_respects_batch_size(monkeypatch: pytest.MonkeyPatch) -> None:
    from kb_ingestion.infrastructure.wiring import build_openai_embedder

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("EMBEDDING_BATCH_SIZE", raising=False)
    defaulted = build_openai_embedder()
    assert defaulted.batch_size == 64
    custom = build_openai_embedder(batch_size=8)
    assert custom.batch_size == 8
