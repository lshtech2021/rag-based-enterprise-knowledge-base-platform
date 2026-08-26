"""Answer a user question with grounded citations."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from kb_domain import Citation
from kb_query.application.ports import (
    EmbedderPort,
    HybridRetrieverPort,
    LLMPort,
    QueryLogPort,
    RerankerPort,
    RetrievalHit,
)
from kb_query.domain.citation_validator import CitationValidator, ValidatedAnswer

_log = logging.getLogger("kb_query.answer_query")


def _truncate(text: str, n: int = 120) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= n:
        return cleaned
    return cleaned[: max(0, n - 3)] + "..."


@dataclass(frozen=True, slots=True)
class AnswerQueryCommand:
    question: str
    top_k: int = 5
    user_id: str | None = None


@dataclass(frozen=True, slots=True)
class AnswerQueryResult:
    rewritten_question: str
    answer: str
    citations: tuple[Citation, ...]
    hits: tuple[RetrievalHit, ...]


class AnswerQuery:
    def __init__(
        self,
        embedder: EmbedderPort,
        retriever: HybridRetrieverPort,
        reranker: RerankerPort,
        llm: LLMPort,
        validator: CitationValidator,
        logs: QueryLogPort | None = None,
    ) -> None:
        self._embedder = embedder
        self._retriever = retriever
        self._reranker = reranker
        self._llm = llm
        self._validator = validator
        self._logs = logs

    async def execute(self, command: AnswerQueryCommand) -> AnswerQueryResult:
        started = time.perf_counter()
        _log.info(
            "event=answer_query.start user_id=%s question=%s top_k=%s",
            command.user_id or "-",
            _truncate(command.question),
            command.top_k,
        )
        try:
            rewritten = await self._llm.rewrite(command.question)
            vector = await self._embedder.embed_query(rewritten)
            hits = await self._retriever.search(rewritten, vector, top_k=command.top_k)
            hits = await self._reranker.rerank(rewritten, hits, top_k=command.top_k)
            draft = await self._llm.generate(command.question, hits)
            validated: ValidatedAnswer = self._validator.validate(draft, hits)
            latency_ms = (time.perf_counter() - started) * 1000
            if self._logs is not None:
                try:
                    await self._logs.save(
                        question=command.question,
                        answer=validated.text,
                        citations=list(validated.citations),
                        retrieved_chunk_ids=[h.chunk.chunk_id for h in hits],
                        user_id=command.user_id,
                        latency_ms=latency_ms,
                    )
                except Exception:  # noqa: BLE001 - logging must never break answers
                    _log.warning(
                        "event=answer_query.query_log_failed user_id=%s",
                        command.user_id or "-",
                        exc_info=True,
                    )
            _log.info(
                "event=answer_query.success user_id=%s hits=%s citations=%s latency_ms=%.1f",
                command.user_id or "-",
                len(hits),
                len(validated.citations),
                latency_ms,
            )
            return AnswerQueryResult(
                rewritten_question=rewritten,
                answer=validated.text,
                citations=validated.citations,
                hits=tuple(hits),
            )
        except Exception:
            _log.exception(
                "event=answer_query.error user_id=%s question=%s",
                command.user_id or "-",
                _truncate(command.question),
            )
            raise
