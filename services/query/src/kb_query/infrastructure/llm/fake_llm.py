"""Deterministic LLM fake that cites retrieved chunks."""

from __future__ import annotations

from collections.abc import Sequence

from kb_query.application.ports import ChatMessage, GeneratedAnswer, RetrievalHit


class FakeLLM:
    async def rewrite(
        self, question: str, *, history: Sequence[ChatMessage] = ()
    ) -> str:
        _ = history
        return question.strip()

    async def generate(
        self,
        question: str,
        hits: list[RetrievalHit],
        *,
        history: Sequence[ChatMessage] = (),
    ) -> GeneratedAnswer:
        _ = question, history
        if not hits:
            return GeneratedAnswer(
                text="I do not have enough grounded evidence to answer.",
                cited_chunk_ids=(),
            )
        top = hits[0]
        snippet = top.chunk.text[:160].strip()
        text = f"Based on the filing, {snippet} [cite:{top.chunk.chunk_id}]"
        return GeneratedAnswer(text=text, cited_chunk_ids=(top.chunk.chunk_id,))


class UngroundedFakeLLM:
    """Produces citations that do not exist — for validator tests."""

    async def rewrite(
        self, question: str, *, history: Sequence[ChatMessage] = ()
    ) -> str:
        _ = history
        return question

    async def generate(
        self,
        question: str,
        hits: list[RetrievalHit],
        *,
        history: Sequence[ChatMessage] = (),
    ) -> GeneratedAnswer:
        _ = question, hits, history
        return GeneratedAnswer(
            text="Earnings doubled overnight [cite:missing-chunk]",
            cited_chunk_ids=("missing-chunk",),
        )
