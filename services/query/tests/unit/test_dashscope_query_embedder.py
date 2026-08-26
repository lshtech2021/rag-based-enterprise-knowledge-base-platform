from __future__ import annotations

import json

import httpx
import pytest
from kb_ingestion.infrastructure.embeddings.dashscope_config import DEFAULT_BASE_URL
from kb_query.infrastructure.embeddings.openai_query_embedder import OpenAIQueryEmbedder


def _embedding_response(vector: list[float]) -> dict:
    return {
        "object": "list",
        "data": [{"object": "embedding", "index": 0, "embedding": vector}],
        "model": "qwen3.7-text-embedding",
        "usage": {"prompt_tokens": 1, "total_tokens": 1},
    }


@pytest.mark.asyncio
async def test_dashscope_query_embedder() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["input"] == "risk factors"
        assert body["model"] == "qwen3.7-text-embedding"
        return httpx.Response(200, json=_embedding_response([0.5, 0.5]))

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


@pytest.mark.asyncio
async def test_dashscope_query_embedder_uses_custom_base_url() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json=_embedding_response([0.5, 0.5]))

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    embedder = OpenAIQueryEmbedder(
        api_key="test-key",
        model="qwen3.7-text-embedding",
        dimensions=2,
        base_url="https://dashscope.example.com/compatible-mode/v1/",
        http_client=http_client,
        api_key_env="DASHSCOPE_API_KEY",
    )
    await embedder.embed_query("risk factors")
    assert seen
    assert seen[0].startswith(
        "https://dashscope.example.com/compatible-mode/v1/embeddings"
    )
    await http_client.aclose()


def test_dashscope_query_embedder_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
        OpenAIQueryEmbedder(api_key_env="DASHSCOPE_API_KEY")
