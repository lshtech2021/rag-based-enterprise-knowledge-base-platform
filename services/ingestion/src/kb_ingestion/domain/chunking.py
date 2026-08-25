"""Pure chunking rules for section-aware splitting."""

from __future__ import annotations

import re
from collections.abc import Iterator


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token) for MVP sizing."""
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, (len(stripped) + 3) // 4)


def split_section_text(
    text: str,
    *,
    target_tokens: int = 768,
    min_tokens: int = 512,
    max_tokens: int = 1024,
    overlap_tokens: int = 64,
) -> list[str]:
    """Split section text into overlapping chunks within the token budget."""
    if estimate_tokens(text) <= max_tokens:
        return [text.strip()] if text.strip() else []

    sentences = _split_sentences(text)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sent_tokens = estimate_tokens(sentence)
        if (
            current
            and current_tokens + sent_tokens > target_tokens
            and current_tokens >= min_tokens
        ):
            chunks.append(" ".join(current).strip())
            overlap = _tail_by_tokens(current, overlap_tokens)
            current = overlap
            current_tokens = estimate_tokens(" ".join(current))
        current.append(sentence)
        current_tokens += sent_tokens
        if current_tokens >= max_tokens:
            chunks.append(" ".join(current).strip())
            overlap = _tail_by_tokens(current, overlap_tokens)
            current = overlap
            current_tokens = estimate_tokens(" ".join(current))

    if current and estimate_tokens(" ".join(current)) > 0:
        chunks.append(" ".join(current).strip())
    return [c for c in chunks if c]


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _tail_by_tokens(sentences: list[str], overlap_tokens: int) -> list[str]:
    if overlap_tokens <= 0 or not sentences:
        return []
    acc: list[str] = []
    total = 0
    for sentence in reversed(sentences):
        t = estimate_tokens(sentence)
        if total + t > overlap_tokens and acc:
            break
        acc.append(sentence)
        total += t
    return list(reversed(acc))


def iter_chunk_payloads(
    sections: list[tuple[str, str]],
    *,
    target_tokens: int = 768,
) -> Iterator[tuple[str, str, int]]:
    """Yield (section_name, chunk_text, token_count)."""
    for name, body in sections:
        for piece in split_section_text(body, target_tokens=target_tokens):
            yield name, piece, estimate_tokens(piece)
