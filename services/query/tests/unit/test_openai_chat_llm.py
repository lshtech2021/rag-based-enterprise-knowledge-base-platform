from __future__ import annotations

import json

import httpx
import pytest
from kb_domain import AccessionNumber, Chunk
from kb_query.application.ports import RetrievalHit
from kb_query.infrastructure.embeddings.openai_query_embedder import OpenAIQueryEmbedder
from kb_query.infrastructure.llm.openai_chat_llm import OpenAIChatLLM


def _chat_response(content: str) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "model": "gpt-4o-mini",
    }


@pytest.mark.asyncio
async def test_openai_chat_llm_rewrite_and_generate() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        user = body["messages"][1]["content"]
        if "Context:" in user:
            content = f"Competition is material [cite:{_chunk().chunk_id}]"
        else:
            content = "competition risks Apple"
        return httpx.Response(200, json=_chat_response(content))

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    llm = OpenAIChatLLM(api_key="test-key", http_client=http_client)

    rewritten = await llm.rewrite("What are risks?")
    assert "competition" in rewritten.lower()

    hit = RetrievalHit(chunk=_chunk(), score=1.0, source_url="https://example.com")
    answer = await llm.generate("What are risks?", [hit])
    assert hit.chunk.chunk_id in answer.cited_chunk_ids
    assert f"[cite:{hit.chunk.chunk_id}]" in answer.text
    await http_client.aclose()


def _chunk() -> Chunk:
    return Chunk(
        chunk_id="0000320193-24-000123:0",
        accession_no=AccessionNumber("0000320193-24-000123"),
        section="Item 1A Risk Factors",
        text="We face substantial competition risks.",
        token_count=10,
    )


@pytest.mark.asyncio
async def test_openai_chat_llm_uses_custom_base_url() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json=_chat_response("rewritten"))

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    llm = OpenAIChatLLM(
        api_key="test-key",
        base_url="https://llm.example.com/v1",
        http_client=http_client,
    )
    await llm.rewrite("hello")
    assert seen
    assert seen[0].startswith("https://llm.example.com/v1/chat/completions")
    await http_client.aclose()


def test_openai_chat_llm_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIChatLLM()


@pytest.mark.asyncio
async def test_chat_and_embeddings_use_different_base_urls() -> None:
    """Chat and embeddings get independent OpenAI-compatible clients."""
    chat_seen: list[str] = []
    embed_seen: list[str] = []

    def chat_handler(request: httpx.Request) -> httpx.Response:
        chat_seen.append(str(request.url))
        return httpx.Response(200, json=_chat_response("rewritten"))

    def embed_handler(request: httpx.Request) -> httpx.Response:
        embed_seen.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2]}],
                "model": "qwen3.7-text-embedding",
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
        )

    chat_http = httpx.AsyncClient(transport=httpx.MockTransport(chat_handler))
    embed_http = httpx.AsyncClient(transport=httpx.MockTransport(embed_handler))
    llm = OpenAIChatLLM(
        api_key="chat-key",
        base_url="https://chat.example.com/v1",
        http_client=chat_http,
    )
    embedder = OpenAIQueryEmbedder(
        api_key="embed-key",
        base_url="https://embed.example.com/compatible-mode/v1",
        dimensions=2,
        http_client=embed_http,
        api_key_env="DASHSCOPE_API_KEY",
    )
    await llm.rewrite("hello")
    await embedder.embed_query("hello")
    assert chat_seen[0].startswith("https://chat.example.com/v1/chat/completions")
    assert embed_seen[0].startswith(
        "https://embed.example.com/compatible-mode/v1/embeddings"
    )
    assert llm.base_url != embedder.base_url
    await chat_http.aclose()
    await embed_http.aclose()
