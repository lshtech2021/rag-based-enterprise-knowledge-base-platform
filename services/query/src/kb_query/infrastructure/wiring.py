"""Build AnswerQuery against local SQLite or Compose (Postgres + OpenSearch)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from kb_ingestion.infrastructure.persistence.postgres_store import PostgresKnowledgeStore
from kb_ingestion.infrastructure.persistence.sqlite_store import SqliteKnowledgeStore
from kb_ingestion.infrastructure.search.opensearch_index import OpenSearchChunkIndex
from kb_query.application.use_cases.answer_query import AnswerQuery
from kb_query.domain.citation_validator import CitationValidator
from kb_query.infrastructure.embeddings.openai_query_embedder import (
    DEFAULT_DIMENSIONS,
    DEFAULT_MODEL,
    OpenAIQueryEmbedder,
)
from kb_query.infrastructure.llm.openai_chat_llm import DEFAULT_CHAT_MODEL, OpenAIChatLLM
from kb_query.infrastructure.rerank.noop_reranker import NoOpReranker
from kb_query.infrastructure.retrieval.compose_hybrid import (
    ComposeHybridRetriever,
    DenseOnlyRetriever,
)
from kb_query.infrastructure.retrieval.in_memory_hybrid import InMemoryHybridRetriever


@dataclass(frozen=True, slots=True)
class QueryRuntime:
    use_case: AnswerQuery
    embedder: OpenAIQueryEmbedder
    llm: OpenAIChatLLM
    corpus_size: int
    knowledge_store: SqliteKnowledgeStore | PostgresKnowledgeStore | None = None
    postgres_store: PostgresKnowledgeStore | None = None


def _resolve_openai_key(openai_api_key: str | None) -> str:
    key = (openai_api_key or os.environ.get("OPENAI_API_KEY", "")).strip()
    if not key:
        raise ValueError("OPENAI_API_KEY is required for query wiring")
    return key


def _resolve_models(
    *,
    embedding_model: str | None,
    chat_model: str | None,
) -> tuple[str, str]:
    resolved_embed = (
        embedding_model or os.environ.get("OPENAI_EMBEDDING_MODEL", "").strip() or DEFAULT_MODEL
    )
    resolved_chat = (
        chat_model or os.environ.get("OPENAI_CHAT_MODEL", "").strip() or DEFAULT_CHAT_MODEL
    )
    return resolved_embed, resolved_chat


async def build_local_answer_query(
    *,
    data_dir: Path,
    openai_api_key: str | None = None,
    openai_base_url: str | None = None,
    embedding_model: str | None = None,
    chat_model: str | None = None,
) -> QueryRuntime:
    """Load SQLite corpus and wire OpenAI embedder + chat LLM for local demo."""
    key = _resolve_openai_key(openai_api_key)
    resolved_embed_model, resolved_chat_model = _resolve_models(
        embedding_model=embedding_model,
        chat_model=chat_model,
    )

    store = SqliteKnowledgeStore(Path(data_dir) / "ingestion.sqlite3")
    corpus = await store.list_retrieval_corpus()
    embedder = OpenAIQueryEmbedder(
        api_key=key,
        model=resolved_embed_model,
        dimensions=DEFAULT_DIMENSIONS,
        base_url=openai_base_url,
    )
    llm = OpenAIChatLLM(api_key=key, model=resolved_chat_model, base_url=openai_base_url)
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
    embedding_model: str | None = None,
    chat_model: str | None = None,
) -> QueryRuntime:
    """Wire OpenAI + pgvector dense + OpenSearch BM25 hybrid retrieval."""
    key = _resolve_openai_key(openai_api_key)
    db_url = (database_url or os.environ.get("DATABASE_URL", "")).strip()
    if not db_url:
        raise ValueError("DATABASE_URL is required for compose query wiring")
    os_url = (opensearch_url or os.environ.get("OPENSEARCH_URL", "http://localhost:9200")).strip()
    resolved_embed_model, resolved_chat_model = _resolve_models(
        embedding_model=embedding_model,
        chat_model=chat_model,
    )

    store = await PostgresKnowledgeStore.connect(db_url)
    # OpenSearch is an optional add-on: compose only *requires* Postgres +
    # MinIO. Unset/unreachable OpenSearch degrades to dense-only retrieval
    # instead of failing wiring.
    retriever: ComposeHybridRetriever | DenseOnlyRetriever
    try:
        search = OpenSearchChunkIndex(url=os_url)
        retriever = ComposeHybridRetriever(dense=store, bm25=search)
    except Exception:  # noqa: BLE001
        retriever = DenseOnlyRetriever(dense=store)
    embedder = OpenAIQueryEmbedder(
        api_key=key,
        model=resolved_embed_model,
        dimensions=DEFAULT_DIMENSIONS,
        base_url=openai_base_url,
    )
    llm = OpenAIChatLLM(api_key=key, model=resolved_chat_model, base_url=openai_base_url)
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
