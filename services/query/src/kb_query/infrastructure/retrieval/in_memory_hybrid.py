"""In-memory hybrid retriever: dense cosine + keyword overlap → RRF."""

from __future__ import annotations

import math
import re

from kb_domain import Chunk
from kb_query.application.ports import HybridRetrieverPort, RetrievalHit
from kb_query.domain.rrf import reciprocal_rank_fusion

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)


class InMemoryHybridRetriever:
    def __init__(self, corpus: list[tuple[Chunk, list[float], str]]) -> None:
        """corpus items: (chunk, embedding, source_url)."""
        self._corpus = corpus

    async def search(
        self,
        query: str,
        query_vector: list[float],
        *,
        top_k: int = 5,
    ) -> list[RetrievalHit]:
        if not self._corpus:
            return []

        dense_scores: list[tuple[str, float]] = []
        sparse_scores: list[tuple[str, float]] = []
        by_id: dict[str, tuple[Chunk, str]] = {}

        q_tokens = set(_TOKEN_RE.findall(query.lower()))
        for chunk, vector, url in self._corpus:
            by_id[chunk.chunk_id] = (chunk, url)
            dense_scores.append((chunk.chunk_id, _cosine(query_vector, vector)))
            c_tokens = set(_TOKEN_RE.findall(chunk.text.lower()))
            overlap = len(q_tokens & c_tokens)
            sparse_scores.append((chunk.chunk_id, float(overlap)))

        dense_ranked = [doc for doc, _ in sorted(dense_scores, key=lambda x: x[1], reverse=True)]
        sparse_ranked = [doc for doc, _ in sorted(sparse_scores, key=lambda x: x[1], reverse=True)]
        fused = reciprocal_rank_fusion([dense_ranked, sparse_ranked])

        hits: list[RetrievalHit] = []
        for doc_id, score in fused[:top_k]:
            chunk, url = by_id[doc_id]
            hits.append(RetrievalHit(chunk=chunk, score=score, source_url=url))
        return hits


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def as_retriever(retriever: InMemoryHybridRetriever) -> HybridRetrieverPort:
    return retriever
