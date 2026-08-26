"""Build AnswerQuery against local SQLite or Compose (Postgres + OpenSearch)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from kb_ingestion.infrastructure.persistence.postgres_store import PostgresKnowledgeStore
from kb_ingestion.infrastructure.persistence.sqlite_store import SqliteKnowledgeStore
from kb_ingestion.infrastructure.search.opensearch_index import OpenSearchChunkIndex
from kb_ingestion.infrastructure.wiring import (
    resolve_embedding_dimensions,
    resolve_embedding_provider,
)
from kb_query.application.use_cases.answer_query import AnswerQuery
from kb_query.domain.citation_validator import CitationValidator
from kb_query.infrastructure.embeddings.dashscope_query_embedder import (
    DEFAULT_MODEL as DASHSCOPE_DEFAULT_MODEL,
)
from kb_query.infrastructure.embeddings.dashscope_query_embedder import (
    DashScopeQueryEmbedder,
)
from kb_query.infrastructure.embeddings.openai_query_embedder import (
    DEFAULT_MODEL as OPENAI_DEFAULT_MODEL,
)
from kb_query.infrastructure.embeddings.openai_query_embedder import (
    OpenAIQueryEmbedder,
)
from kb_query.infrastructure.llm.openai_chat_llm import DEFAULT_CHAT_MODEL, OpenAIChatLLM
from kb_query.infrastructure.rerank.noop_reranker import NoOpReranker
from kb_query.infrastructure.retrieval.compose_hybrid import (
    ComposeHybridRetriever,
    DenseOnlyRetriever,
)
from kb_query.infrastructure.retrieval.in_memory_hybrid import InMemoryHybridRetriever


class QueryEmbedder(Protocol):
    @property
    def model(self) -> str: ...

    async def embed_query(self, text: str) -> list[float]: ...

    async def aclose(self) -> None: ...


@dataclass(frozen=True, slots=True)
class QueryRuntime:
    use_case: AnswerQuery
    embedder: QueryEmbedder
    llm: OpenAIChatLLM
    corpus_size: int
    knowledge_store: SqliteKnowledgeStore | PostgresKnowledgeStore | None = None
    postgres_store: PostgresKnowledgeStore | None = None


def _resolve_openai_key(openai_api_key: str | None) -> str:
    key = (openai_api_key or os.environ.get("OPENAI_API_KEY", "")).strip()
    if not key:
        raise ValueError("OPENAI_API_KEY is required for query chat LLM wiring")
    return key


def _resolve_chat_model(chat_model: str | None) -> str:
    return chat_model or os.environ.get("OPENAI_CHAT_MODEL", "").strip() or DEFAULT_CHAT_MODEL


def _build_query_embedder(
    *,
    embedding_provider: str | None,
    embedding_model: str | None,
    embedding_dimensions: int | None,
    openai_api_key: str | None,
    openai_base_url: str | None,
    dashscope_api_key: str | None,
    dashscope_base_url: str | None,
) -> QueryEmbedder:
    provider = resolve_embedding_provider(embedding_provider)
    dims = resolve_embedding_dimensions(embedding_dimensions, provider=provider)
    if provider == "dashscope":
        model = (
            embedding_model
            or os.environ.get("DASHSCOPE_EMBEDDING_MODEL", "").strip()
            or DASHSCOPE_DEFAULT_MODEL
        )
        key = (dashscope_api_key or os.environ.get("DASHSCOPE_API_KEY", "")).strip()
        return DashScopeQueryEmbedder(
            api_key=key or None,
            model=model,
            dimensions=dims,
            base_url=dashscope_base_url,
        )
    model = (
        embedding_model
        or os.environ.get("OPENAI_EMBEDDING_MODEL", "").strip()
        or OPENAI_DEFAULT_MODEL
    )
    return OpenAIQueryEmbedder(
        api_key=_resolve_openai_key(openai_api_key),
        model=model,
        dimensions=dims,
        base_url=openai_base_url,
    )


async def build_local_answer_query(
    *,
    data_dir: Path,
    openai_api_key: str | None = None,
    openai_base_url: str | None = None,
    embedding_provider: str | None = None,
    embedding_model: str | None = None,
    embedding_dimensions: int | None = None,
    dashscope_api_key: str | None = None,
    dashscope_base_url: str | None = None,
    chat_model: str | None = None,
) -> QueryRuntime:
    """Load SQLite corpus and wire embedder + OpenAI chat LLM for local demo."""
    chat_key = _resolve_openai_key(openai_api_key)
    resolved_chat_model = _resolve_chat_model(chat_model)

    store = SqliteKnowledgeStore(Path(data_dir) / "ingestion.sqlite3")
    corpus = await store.list_retrieval_corpus()
    embedder = _build_query_embedder(
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
        openai_api_key=openai_api_key,
        openai_base_url=openai_base_url,
        dashscope_api_key=dashscope_api_key,
        dashscope_base_url=dashscope_base_url,
    )
    llm = OpenAIChatLLM(api_key=chat_key, model=resolved_chat_model, base_url=openai_base_url)
    use_case = AnswerQuery(
        embedder=embedder,
        retriever=InMemoryHybridRetriever(corpus),
        reranker=NoOpReranker(),
        llm=llm,
        validator=CitationValidator(),
    )
    return QueryRuntime(
        use_case=use_case,
        embedder=embedder,
        llm=llm,
        corpus_size=len(corpus),
        knowledge_store=store,
    )


async def build_compose_answer_query(
    *,
    openai_api_key: str | None = None,
    openai_base_url: str | None = None,
    database_url: str | None = None,
    opensearch_url: str | None = None,
    opensearch_username: str | None = None,
    opensearch_password: str | None = None,
    embedding_provider: str | None = None,
    embedding_model: str | None = None,
    embedding_dimensions: int | None = None,
    dashscope_api_key: str | None = None,
    dashscope_base_url: str | None = None,
    chat_model: str | None = None,
) -> QueryRuntime:
    """Wire embedder + chat LLM + pgvector dense + optional OpenSearch BM25."""
    chat_key = _resolve_openai_key(openai_api_key)
    db_url = (database_url or os.environ.get("DATABASE_URL", "")).strip()
    if not db_url:
        raise ValueError("DATABASE_URL is required for compose query wiring")
    os_url = (opensearch_url or os.environ.get("OPENSEARCH_URL", "http://localhost:9200")).strip()
    os_user = (
        opensearch_username
        if opensearch_username is not None
        else os.environ.get("OPENSEARCH_USERNAME", "")
    ).strip()
    os_password = (
        opensearch_password
        if opensearch_password is not None
        else os.environ.get("OPENSEARCH_PASSWORD", "")
    ).strip()
    resolved_chat_model = _resolve_chat_model(chat_model)

    store = await PostgresKnowledgeStore.connect(db_url)
    # OpenSearch is an optional add-on: compose only *requires* Postgres +
    # MinIO. Unset/unreachable OpenSearch degrades to dense-only retrieval
    # instead of failing wiring.
    retriever: ComposeHybridRetriever | DenseOnlyRetriever
    try:
        search = OpenSearchChunkIndex(
            url=os_url,
            username=os_user or None,
            password=os_password or None,
        )
        retriever = ComposeHybridRetriever(dense=store, bm25=search)
    except Exception:  # noqa: BLE001
        retriever = DenseOnlyRetriever(dense=store)
    embedder = _build_query_embedder(
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
        openai_api_key=openai_api_key,
        openai_base_url=openai_base_url,
        dashscope_api_key=dashscope_api_key,
        dashscope_base_url=dashscope_base_url,
    )
    llm = OpenAIChatLLM(api_key=chat_key, model=resolved_chat_model, base_url=openai_base_url)
    use_case = AnswerQuery(
        embedder=embedder,
        retriever=retriever,
        reranker=NoOpReranker(),
        llm=llm,
        validator=CitationValidator(),
        # `store` also implements QueryLogPort.save — persists `query_logs`
        # (architecture §7) on the same pool used for dense retrieval.
        logs=store,
    )
    return QueryRuntime(
        use_case=use_case,
        embedder=embedder,
        llm=llm,
        corpus_size=await store.corpus_chunk_count(),
        knowledge_store=store,
        postgres_store=store,
    )
