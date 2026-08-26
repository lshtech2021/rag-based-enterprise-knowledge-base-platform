from __future__ import annotations

import httpx
import pytest
from kb_query.infrastructure.embeddings.openai_query_embedder import OpenAIQueryEmbedder


@pytest.mark.asyncio
async def test_openai_query_embedder() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.5, 0.5]}]},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="https://api.openai.com")
    embedder = OpenAIQueryEmbedder(api_key="test-key", dimensions=2, client=client)
    vector = await embedder.embed_query("risk factors")
    assert vector == [0.5, 0.5]
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_query_embedder_uses_custom_base_url() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.5, 0.5]}]},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    embedder = OpenAIQueryEmbedder(
        api_key="test-key",
        dimensions=2,
        base_url="https://llm.example.com/v1/",
        client=client,
    )
    await embedder.embed_query("risk factors")
    assert seen
    assert seen[0].startswith("https://llm.example.com/v1/embeddings")
    await client.aclose()


def test_openai_query_embedder_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIQueryEmbedder()
