"""Query application ports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from kb_domain import Chunk, Citation


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    chunk: Chunk
    score: float
    source_url: str


@dataclass(frozen=True, slots=True)
class GeneratedAnswer:
    text: str
    cited_chunk_ids: tuple[str, ...]


@runtime_checkable
class EmbedderPort(Protocol):
    async def embed_query(self, text: str) -> list[float]: ...


@runtime_checkable
class HybridRetrieverPort(Protocol):
    async def search(
        self,
        query: str,
        query_vector: list[float],
        *,
        top_k: int = 5,
    ) -> list[RetrievalHit]: ...


@runtime_checkable
class RerankerPort(Protocol):
    async def rerank(
        self, query: str, hits: list[RetrievalHit], *, top_k: int = 5
    ) -> list[RetrievalHit]: ...


@runtime_checkable
class LLMPort(Protocol):
    async def rewrite(self, question: str) -> str: ...

    async def generate(self, question: str, hits: list[RetrievalHit]) -> GeneratedAnswer: ...


@runtime_checkable
class QueryLogPort(Protocol):
    async def save(
        self,
        *,
        question: str,
        answer: str,
        citations: list[Citation],
        retrieved_chunk_ids: list[str],
    ) -> None: ...
