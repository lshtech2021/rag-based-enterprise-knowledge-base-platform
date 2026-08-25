"""Offline citation faithfulness heuristic (Ragas stand-in for CI)."""

from __future__ import annotations

import re

_CITE_RE = re.compile(r"\[cite:([^\]]+)\]")


def citation_faithfulness_score(*, answer: str, allowed_chunk_ids: set[str]) -> float:
    """Return 1.0 if all cite markers resolve to allowed chunks and at least one exists.

    Returns 0.0 when uncited or when any citation is unknown.
    """
    markers = _CITE_RE.findall(answer)
    if not markers:
        return 0.0
    if any(cid not in allowed_chunk_ids for cid in markers):
        return 0.0
    return 1.0


def assert_faithful(*, answer: str, allowed_chunk_ids: set[str]) -> None:
    score = citation_faithfulness_score(answer=answer, allowed_chunk_ids=allowed_chunk_ids)
    if score < 1.0:
        raise AssertionError(f"Citation faithfulness failed (score={score}) for answer={answer!r}")
