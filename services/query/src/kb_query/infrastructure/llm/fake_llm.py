"""Deterministic LLM fake that cites retrieved chunks."""

from __future__ import annotations

from kb_query.application.ports import GeneratedAnswer, RetrievalHit


class FakeLLM:
    async def rewrite(self, question: str) -> str:
        return question.strip()

    async def generate(self, question: str, hits: list[RetrievalHit]) -> GeneratedAnswer:
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

    async def rewrite(self, question: str) -> str:
        return question

    async def generate(self, question: str, hits: list[RetrievalHit]) -> GeneratedAnswer:
        return GeneratedAnswer(
            text="Earnings doubled overnight [cite:missing-chunk]",
            cited_chunk_ids=("missing-chunk",),
        )
