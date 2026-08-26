from __future__ import annotations

import json

import httpx
import pytest
from kb_ingestion.infrastructure.embeddings.dashscope_embedder import DashScopeEmbedder


@pytest.mark.asyncio
async def test_dashscope_embedder_batches_and_orders() -> None:
    seen_bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(
            "/api/v1/services/embeddings/text-embedding/text-embedding"
        )
        body = json.loads(request.content)
        seen_bodies.append(body)
        assert body["model"] == "qwen3.7-text-embedding"
        assert body["parameters"]["text_type"] == "document"
        assert body["parameters"]["dimension"] == 2
        return httpx.Response(
            200,
            json={
                "status_code": 200,
                "output": {
                    "embeddings": [
                        {"text_index": 1, "embedding": [0.0, 1.0]},
                        {"text_index": 0, "embedding": [1.0, 0.0]},
                    ]
                },
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    embedder = DashScopeEmbedder(
        api_key="test-key",
        dimensions=2,
        client=client,
    )
    vectors = await embedder.embed_documents(["a", "b"])
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]
    assert embedder.model == "qwen3.7-text-embedding"
    assert seen_bodies[0]["input"]["texts"] == ["a", "b"]
    await client.aclose()


@pytest.mark.asyncio
async def test_dashscope_embedder_uses_custom_base_url() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "status_code": 200,
                "output": {"embeddings": [{"text_index": 0, "embedding": [1.0, 0.0]}]},
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    embedder = DashScopeEmbedder(
        api_key="test-key",
        dimensions=2,
        base_url="https://dashscope.example.com/",
        client=client,
    )
    await embedder.embed_documents(["a"])
    assert seen
    assert seen[0].startswith(
        "https://dashscope.example.com/api/v1/services/embeddings/text-embedding/text-embedding"
    )
    await client.aclose()


def test_dashscope_embedder_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
        DashScopeEmbedder()


def test_resolve_embedding_provider_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    from kb_ingestion.infrastructure.wiring import resolve_embedding_provider

    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    assert resolve_embedding_provider("qwen") == "dashscope"
    assert resolve_embedding_provider("dashscope") == "dashscope"
    assert resolve_embedding_provider("openai") == "openai"
    with pytest.raises(ValueError, match="Unsupported EMBEDDING_PROVIDER"):
        resolve_embedding_provider("unknown")


def test_build_dashscope_embedder_passes_model(monkeypatch: pytest.MonkeyPatch) -> None:
    from kb_ingestion.infrastructure.wiring import build_dashscope_embedder

    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    embedder = build_dashscope_embedder(
        model="qwen3.7-text-embedding",
        base_url="https://dashscope.example.com",
        dimensions=1536,
    )
    assert embedder.model == "qwen3.7-text-embedding"
    assert embedder.dimensions == 1536
    assert embedder._base_url == "https://dashscope.example.com"  # noqa: SLF001
