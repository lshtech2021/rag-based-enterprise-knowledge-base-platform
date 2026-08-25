"""Pass-through reranker (cross-encoder deferred)."""

from __future__ import annotations

from kb_query.application.ports import RetrievalHit


class NoOpReranker:
    async def rerank(
        self, query: str, hits: list[RetrievalHit], *, top_k: int = 5
    ) -> list[RetrievalHit]:
        return hits[:top_k]
