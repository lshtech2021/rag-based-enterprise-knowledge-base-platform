import asyncio

from fastapi.testclient import TestClient
from kb_bff.main import create_app
from kb_bff.query_router import get_answer_query
from kb_domain import AccessionNumber, Chunk
from kb_query.application.use_cases.answer_query import AnswerQuery
from kb_query.domain.citation_validator import CitationValidator
from kb_query.infrastructure.embeddings.hash_query_embedder import HashQueryEmbedder
from kb_query.infrastructure.llm.fake_llm import FakeLLM
from kb_query.infrastructure.rerank.noop_reranker import NoOpReranker
from kb_query.infrastructure.retrieval.in_memory_hybrid import InMemoryHybridRetriever


def _use_case() -> AnswerQuery:
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


def test_healthz_reports_tracing_backend() -> None:
    client = TestClient(create_app())
    body = client.get("/healthz").json()
    assert body["tracing"] == "otel-inmemory"


def test_query_records_observer_events_and_spans() -> None:
    app = create_app()
    app.state.answer_query = _use_case()
    client = TestClient(app)
    with client.stream(
        "POST",
        "/v1/query",
        json={"question": "What competition risks are disclosed?"},
    ) as response:
        assert response.status_code == 200
        _ = "".join(response.iter_text())

    events = app.state.llm_observer.events()
    assert any(event.kind == "retrieval" for event in events)
    assert any(event.kind == "generation" for event in events)
    spans = app.state.tracer.finished_spans()
    names = {span.name for span in spans}
    assert "http.request" in names
    assert "query.answer" in names


def test_query_dependency_override_still_works() -> None:
    app = create_app()
    app.dependency_overrides[get_answer_query] = _use_case
    client = TestClient(app)
    with client.stream("POST", "/v1/query", json={"question": "competition risks"}) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    assert "data: " in body
