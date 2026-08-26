"""Hybrid retriever: pgvector dense + OpenSearch BM25 → RRF."""

from __future__ import annotations

from typing import Protocol

from kb_domain import Chunk
from kb_query.application.ports import HybridRetrieverPort, RetrievalHit
from kb_query.domain.rrf import reciprocal_rank_fusion


class DenseSearcher(Protocol):
    async def search_dense(
        self, query_vector: list[float], *, top_k: int = 5
    ) -> list[tuple[Chunk, float, str]]: ...


class Bm25Searcher(Protocol):
    async def search_bm25(
        self, query: str, *, top_k: int = 5
    ) -> list[tuple[Chunk, float, str]]: ...


class ComposeHybridRetriever:
    """Fuse pgvector nearest-neighbor ranks with OpenSearch BM25 ranks."""

    def __init__(self, dense: DenseSearcher, bm25: Bm25Searcher) -> None:
        self._dense = dense
        self._bm25 = bm25

    async def search(
        self,
        query: str,
        query_vector: list[float],
        *,
        top_k: int = 5,
    ) -> list[RetrievalHit]:
        fetch_k = max(top_k * 3, top_k)
        dense_hits = await self._dense.search_dense(query_vector, top_k=fetch_k)
        bm25_hits = await self._bm25.search_bm25(query, top_k=fetch_k)

        by_id: dict[str, tuple[Chunk, str]] = {}
        for chunk, _score, url in dense_hits + bm25_hits:
            by_id[chunk.chunk_id] = (chunk, url)

        dense_ranked = [chunk.chunk_id for chunk, _, _ in dense_hits]
        bm25_ranked = [chunk.chunk_id for chunk, _, _ in bm25_hits]
        fused = reciprocal_rank_fusion([dense_ranked, bm25_ranked])

        hits: list[RetrievalHit] = []
        for doc_id, score in fused[:top_k]:
            chunk, url = by_id[doc_id]
            hits.append(RetrievalHit(chunk=chunk, score=score, source_url=url))
        return hits


def as_retriever(retriever: ComposeHybridRetriever) -> HybridRetrieverPort:
    return retriever


class DenseOnlyRetriever:
    """pgvector-only fallback when OpenSearch is unset/unreachable.

    Compose only *requires* Postgres/pgvector + MinIO; OpenSearch is an
    optional add-on for the BM25 half of hybrid retrieval (SPEC-query).
    """

    def __init__(self, dense: DenseSearcher) -> None:
        self._dense = dense

    async def search(
        self,
        query: str,
        query_vector: list[float],
        *,
        top_k: int = 5,
    ) -> list[RetrievalHit]:
        hits = await self._dense.search_dense(query_vector, top_k=top_k)
        return [
            RetrievalHit(chunk=chunk, score=score, source_url=url) for chunk, score, url in hits
        ]
