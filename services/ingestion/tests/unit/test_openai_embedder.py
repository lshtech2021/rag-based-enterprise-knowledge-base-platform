from __future__ import annotations

import httpx
import pytest
from kb_ingestion.infrastructure.embeddings.openai_embedder import OpenAIEmbedder


@pytest.mark.asyncio
async def test_openai_embedder_batches_and_orders() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/embeddings"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="https://api.openai.com")
    embedder = OpenAIEmbedder(
        api_key="test-key",
        dimensions=2,
        client=client,
    )
    vectors = await embedder.embed_documents(["a", "b"])
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]
    assert embedder.dimensions == 2
    assert embedder.model == "text-embedding-3-small"
    await client.aclose()


def test_openai_embedder_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIEmbedder()
