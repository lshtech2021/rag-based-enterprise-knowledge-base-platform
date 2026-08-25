import pytest
from kb_domain import AccessionNumber, Chunk
from kb_query.application.use_cases.answer_query import AnswerQuery, AnswerQueryCommand
from kb_query.domain.citation_validator import CitationValidator, UngroundedAnswerError
from kb_query.infrastructure.embeddings.hash_query_embedder import HashQueryEmbedder
from kb_query.infrastructure.llm.fake_llm import FakeLLM, UngroundedFakeLLM
from kb_query.infrastructure.rerank.noop_reranker import NoOpReranker
from kb_query.infrastructure.retrieval.in_memory_hybrid import InMemoryHybridRetriever
from kb_query.presentation.graph import build_answer_graph, build_staged_graph


async def _seeded_use_case(llm: FakeLLM | UngroundedFakeLLM | None = None) -> AnswerQuery:
    embedder = HashQueryEmbedder(dimensions=32)
    chunk = Chunk(
        chunk_id="risk-1",
        accession_no=AccessionNumber("0000320193-24-000123"),
        section="Item 1A Risk Factors",
        text="We face substantial competition risks in consumer markets worldwide.",
        token_count=20,
    )
    vector = await embedder.embed_query(chunk.text)
    retriever = InMemoryHybridRetriever(
        [(chunk, vector, "https://www.sec.gov/Archives/example.htm")]
    )
    return AnswerQuery(
        embedder=embedder,
        retriever=retriever,
        reranker=NoOpReranker(),
        llm=llm or FakeLLM(),
        validator=CitationValidator(),
    )


@pytest.mark.asyncio
async def test_answer_query_returns_grounded_citation() -> None:
    uc = await _seeded_use_case()
    result = await uc.execute(AnswerQueryCommand(question="What competition risks are disclosed?"))
    assert result.citations
    assert result.citations[0].chunk_id == "risk-1"
    assert "[cite:risk-1]" in result.answer


@pytest.mark.asyncio
async def test_answer_query_rejects_ungrounded_llm() -> None:
    uc = await _seeded_use_case(llm=UngroundedFakeLLM())
    with pytest.raises(UngroundedAnswerError):
        await uc.execute(AnswerQueryCommand(question="Anything"))


@pytest.mark.asyncio
async def test_langgraph_answer_entrypoint() -> None:
    uc = await _seeded_use_case()
    graph = build_answer_graph(uc)
    out = await graph.ainvoke({"question": "What competition risks are disclosed?"})
    assert out["citations"][0]["chunk_id"] == "risk-1"


@pytest.mark.asyncio
async def test_langgraph_four_stages() -> None:
    async def rewrite(q: str) -> str:
        return q.upper()

    async def retrieve(q: str) -> list[str]:
        return ["hit"]

    async def generate(q: str, hits: list[str]) -> str:
        return f"{q}:{hits[0]}"

    def validate(answer: str, hits: list[str]) -> str:
        return answer + ":ok"

    graph = build_staged_graph(
        rewrite_fn=rewrite,
        retrieve_fn=retrieve,
        generate_fn=generate,
        validate_fn=validate,
    )
    out = await graph.ainvoke({"question": "hi"})
    assert out["rewritten"] == "HI"
    assert out["answer"] == "hi:hit:ok"
