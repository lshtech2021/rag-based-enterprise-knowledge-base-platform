from __future__ import annotations

import httpx
import pytest
from kb_query.infrastructure.embeddings.openai_query_embedder import OpenAIQueryEmbedder


def _embedding_response(vector: list[float]) -> dict:
    return {
        "object": "list",
        "data": [{"object": "embedding", "index": 0, "embedding": vector}],
        "model": "text-embedding-3-small",
        "usage": {"prompt_tokens": 1, "total_tokens": 1},
    }


@pytest.mark.asyncio
async def test_openai_query_embedder() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_embedding_response([0.5, 0.5]))

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    embedder = OpenAIQueryEmbedder(
        api_key="test-key", dimensions=2, http_client=http_client
    )
    vector = await embedder.embed_query("risk factors")
    assert vector == [0.5, 0.5]
    await http_client.aclose()


@pytest.mark.asyncio
async def test_openai_query_embedder_uses_custom_base_url() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json=_embedding_response([0.5, 0.5]))

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    embedder = OpenAIQueryEmbedder(
        api_key="test-key",
        dimensions=2,
        base_url="https://llm.example.com/v1/",
        http_client=http_client,
    )
    await embedder.embed_query("risk factors")
    assert seen
    assert seen[0].startswith("https://llm.example.com/v1/embeddings")
    await http_client.aclose()


def test_openai_query_embedder_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIQueryEmbedder()
