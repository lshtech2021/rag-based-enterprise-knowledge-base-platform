"""Answer a user question with grounded citations."""

from __future__ import annotations

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


@dataclass(frozen=True, slots=True)
class AnswerQueryCommand:
    question: str
    top_k: int = 5


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
        rewritten = await self._llm.rewrite(command.question)
        vector = await self._embedder.embed_query(rewritten)
        hits = await self._retriever.search(rewritten, vector, top_k=command.top_k)
        hits = await self._reranker.rerank(rewritten, hits, top_k=command.top_k)
        draft = await self._llm.generate(command.question, hits)
        validated: ValidatedAnswer = self._validator.validate(draft, hits)
        if self._logs is not None:
            await self._logs.save(
                question=command.question,
                answer=validated.text,
                citations=list(validated.citations),
                retrieved_chunk_ids=[h.chunk.chunk_id for h in hits],
            )
        return AnswerQueryResult(
            rewritten_question=rewritten,
            answer=validated.text,
            citations=validated.citations,
            hits=tuple(hits),
        )
