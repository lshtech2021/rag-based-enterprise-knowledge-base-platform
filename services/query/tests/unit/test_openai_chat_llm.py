from __future__ import annotations

import json

import httpx
import pytest
from kb_domain import AccessionNumber, Chunk
from kb_query.application.ports import ChatMessage, RetrievalHit
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
                "model": "text-embedding-3-small",
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
        base_url="https://embed.example.com/v1",
        dimensions=2,
        http_client=embed_http,
    )
    await llm.rewrite("hello")
    await embedder.embed_query("hello")
    assert chat_seen[0].startswith("https://chat.example.com/v1/chat/completions")
    assert embed_seen[0].startswith("https://embed.example.com/v1/embeddings")
    assert llm.base_url != embedder.base_url
    await chat_http.aclose()
    await embed_http.aclose()


@pytest.mark.asyncio
async def test_openai_chat_llm_rewrite_uses_history() -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        return httpx.Response(200, json=_chat_response("Apple competition risks Item 1A"))

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    llm = OpenAIChatLLM(api_key="test-key", http_client=http_client)
    history = (
        ChatMessage(role="user", content="Tell me about Apple risks"),
        ChatMessage(role="assistant", content="Several risks are disclosed."),
    )
    rewritten = await llm.rewrite("What about that?", history=history)
    assert "competition" in rewritten.lower() or "Apple" in rewritten
    user = seen[0]["messages"][1]["content"]
    assert "Prior conversation:" in user
    assert "Current question: What about that?" in user
    assert "Tell me about Apple risks" in user
    await http_client.aclose()


@pytest.mark.asyncio
async def test_openai_chat_llm_generate_includes_history_messages() -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        return httpx.Response(
            200,
            json=_chat_response(f"Follow-up grounded [cite:{_chunk().chunk_id}]"),
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    llm = OpenAIChatLLM(api_key="test-key", http_client=http_client)
    history = (
        ChatMessage(role="user", content="What competition risks?"),
        ChatMessage(role="assistant", content="Competition is material."),
    )
    hit = RetrievalHit(chunk=_chunk(), score=1.0, source_url="https://example.com")
    answer = await llm.generate("Say more", [hit], history=history)
    assert hit.chunk.chunk_id in answer.cited_chunk_ids
    messages = seen[0]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "What competition risks?"}
    assert messages[2] == {"role": "assistant", "content": "Competition is material."}
    assert messages[3]["role"] == "user"
    assert "Context:" in messages[3]["content"]
    assert "Question: Say more" in messages[3]["content"]
    await http_client.aclose()
