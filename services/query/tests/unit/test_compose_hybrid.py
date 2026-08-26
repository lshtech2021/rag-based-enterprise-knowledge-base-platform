from __future__ import annotations

import pytest
from kb_domain import AccessionNumber, Chunk
from kb_query.infrastructure.retrieval.compose_hybrid import ComposeHybridRetriever


class FakeDense:
    def __init__(self, hits: list[tuple[Chunk, float, str]]) -> None:
        self._hits = hits

    async def search_dense(
        self, query_vector: list[float], *, top_k: int = 5
    ) -> list[tuple[Chunk, float, str]]:
        return self._hits[:top_k]


class FakeBm25:
    def __init__(self, hits: list[tuple[Chunk, float, str]]) -> None:
        self._hits = hits

    async def search_bm25(self, query: str, *, top_k: int = 5) -> list[tuple[Chunk, float, str]]:
        return self._hits[:top_k]


def _chunk(cid: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=cid,
        accession_no=AccessionNumber("0000320193-24-000123"),
        section="Item 1A",
        text=text,
        token_count=5,
    )


@pytest.mark.asyncio
async def test_compose_hybrid_rrf_orders_shared_hits_first() -> None:
    a = _chunk("a", "competition risks")
    b = _chunk("b", "revenue growth")
    c = _chunk("c", "other")
    dense = FakeDense([(a, 0.9, "u"), (b, 0.5, "u")])
    bm25 = FakeBm25([(b, 10.0, "u"), (c, 5.0, "u")])
    retriever = ComposeHybridRetriever(dense=dense, bm25=bm25)
    hits = await retriever.search("competition", [0.1, 0.2], top_k=3)
    ids = [h.chunk.chunk_id for h in hits]
    assert ids[0] == "b"
    assert set(ids) == {"a", "b", "c"}
