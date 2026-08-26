from __future__ import annotations

import json

import httpx
import pytest
from kb_domain import AccessionNumber, Chunk
from kb_query.application.ports import RetrievalHit
from kb_query.infrastructure.llm.openai_chat_llm import OpenAIChatLLM


@pytest.mark.asyncio
async def test_openai_chat_llm_rewrite_and_generate() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        user = body["messages"][1]["content"]
        if "Context:" in user:
            content = f"Competition is material [cite:{_chunk().chunk_id}]"
        else:
            content = "competition risks Apple"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="https://api.openai.com")
    llm = OpenAIChatLLM(api_key="test-key", client=client)

    rewritten = await llm.rewrite("What are risks?")
    assert "competition" in rewritten.lower()

    hit = RetrievalHit(chunk=_chunk(), score=1.0, source_url="https://example.com")
    answer = await llm.generate("What are risks?", [hit])
    assert hit.chunk.chunk_id in answer.cited_chunk_ids
    assert f"[cite:{hit.chunk.chunk_id}]" in answer.text
    await client.aclose()


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
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "rewritten"}}]},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    llm = OpenAIChatLLM(
        api_key="test-key",
        base_url="https://llm.example.com/v1",
        client=client,
    )
    await llm.rewrite("hello")
    assert seen
    assert seen[0].startswith("https://llm.example.com/v1/chat/completions")
    await client.aclose()


def test_openai_chat_llm_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIChatLLM()
