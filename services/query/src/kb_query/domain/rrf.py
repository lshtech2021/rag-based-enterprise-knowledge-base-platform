"""Reciprocal Rank Fusion helpers."""

from __future__ import annotations


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    *,
    k: int = 60,
) -> list[tuple[str, float]]:
    """Fuse multiple ranked id lists into (id, score) descending."""
    scores: dict[str, float] = {}
    for ranking in ranked_lists:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)
