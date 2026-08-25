import pytest
from kb_domain import AccessionNumber, Chunk
from kb_query.infrastructure.embeddings.hash_query_embedder import HashQueryEmbedder
from kb_query.infrastructure.retrieval.in_memory_hybrid import InMemoryHybridRetriever


@pytest.mark.asyncio
async def test_hybrid_retriever_returns_relevant_chunk() -> None:
    embedder = HashQueryEmbedder(dimensions=32)
    risk = Chunk(
        chunk_id="risk-1",
        accession_no=AccessionNumber("0000320193-24-000123"),
        section="Item 1A Risk Factors",
        text="We face substantial competition risks in consumer markets.",
        token_count=20,
    )
    other = Chunk(
        chunk_id="other-1",
        accession_no=AccessionNumber("0000320193-24-000123"),
        section="Item 8 Financial Statements",
        text="Cash and cash equivalents were stable.",
        token_count=12,
    )
    corpus = [
        (risk, await embedder.embed_query("competition risks"), "https://example.com/r"),
        (other, await embedder.embed_query(other.text), "https://example.com/o"),
    ]
    retriever = InMemoryHybridRetriever(corpus)
    q = "competition risks"
    hits = await retriever.search(q, await embedder.embed_query(q), top_k=2)
    assert hits
    assert hits[0].chunk.chunk_id == "risk-1"
