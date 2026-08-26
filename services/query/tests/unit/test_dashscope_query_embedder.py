from __future__ import annotations

import json

import httpx
import pytest
from kb_query.infrastructure.embeddings.dashscope_query_embedder import (
    DashScopeQueryEmbedder,
)


@pytest.mark.asyncio
async def test_dashscope_query_embedder() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["parameters"]["text_type"] == "query"
        assert body["input"]["texts"] == ["risk factors"]
        return httpx.Response(
            200,
            json={
                "status_code": 200,
                "output": {"embeddings": [{"text_index": 0, "embedding": [0.5, 0.5]}]},
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    embedder = DashScopeQueryEmbedder(api_key="test-key", dimensions=2, client=client)
    vector = await embedder.embed_query("risk factors")
    assert vector == [0.5, 0.5]
    assert embedder.model == "qwen3.7-text-embedding"
    await client.aclose()


@pytest.mark.asyncio
async def test_dashscope_query_embedder_uses_custom_base_url() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "status_code": 200,
                "output": {"embeddings": [{"text_index": 0, "embedding": [0.5, 0.5]}]},
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    embedder = DashScopeQueryEmbedder(
        api_key="test-key",
        dimensions=2,
        base_url="https://dashscope.example.com/",
        client=client,
    )
    await embedder.embed_query("risk factors")
    assert seen
    assert seen[0].startswith(
        "https://dashscope.example.com/api/v1/services/embeddings/text-embedding/text-embedding"
    )
    await client.aclose()


def test_dashscope_query_embedder_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
        DashScopeQueryEmbedder()
