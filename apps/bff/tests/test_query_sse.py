import asyncio
import json

from fastapi.testclient import TestClient
from kb_bff.main import create_app
from kb_domain import AccessionNumber, Chunk
from kb_query.application.use_cases.answer_query import AnswerQuery
from kb_query.domain.citation_validator import CitationValidator
from kb_query.infrastructure.embeddings.hash_query_embedder import HashQueryEmbedder
from kb_query.infrastructure.llm.fake_llm import FakeLLM
from kb_query.infrastructure.rerank.noop_reranker import NoOpReranker
from kb_query.infrastructure.retrieval.in_memory_hybrid import InMemoryHybridRetriever


def _build_use_case() -> AnswerQuery:
    embedder = HashQueryEmbedder(dimensions=32)
    chunk = Chunk(
        chunk_id="risk-1",
        accession_no=AccessionNumber("0000320193-24-000123"),
        section="Item 1A Risk Factors",
        text="We face substantial competition risks in consumer markets worldwide.",
        token_count=20,
    )
    vector = asyncio.run(embedder.embed_query(chunk.text))
    return AnswerQuery(
        embedder=embedder,
        retriever=InMemoryHybridRetriever(
            [(chunk, vector, "https://www.sec.gov/Archives/example.htm")]
        ),
        reranker=NoOpReranker(),
        llm=FakeLLM(),
        validator=CitationValidator(),
    )


def test_query_sse_streams_tokens_sources_done() -> None:
    app = create_app()
    app.state.answer_query = _build_use_case()
    client = TestClient(app)
    with client.stream(
        "POST",
        "/v1/query",
        json={"question": "What competition risks are disclosed?"},
    ) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = "".join(response.iter_text())

    events = []
    for line in body.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line.removeprefix("data: ")))
    types = [e["type"] for e in events]
    assert "token" in types
    assert "sources" in types
    assert "done" in types
    sources = next(e for e in events if e["type"] == "sources")["data"]
    assert sources[0]["chunk_id"] == "risk-1"
