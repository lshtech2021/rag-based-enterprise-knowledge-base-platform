"""Build a fully wired IngestFiling for local, memory, or compose backends."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from kb_application_ports import ObjectStorePort
from kb_ingestion.application.ports import EmbedderPort, FilingRepository, SearchIndexPort
from kb_ingestion.application.use_cases.ingest_filing import IngestFiling
from kb_ingestion.infrastructure.edgar.http_client import HttpEdgarClient
from kb_ingestion.infrastructure.embeddings.hash_embedder import HashEmbedder
from kb_ingestion.infrastructure.embeddings.openai_embedder import (
    DEFAULT_DIMENSIONS,
    DEFAULT_MODEL,
    OpenAIEmbedder,
    require_openai_api_key,
)
from kb_ingestion.infrastructure.object_store.local_fs import LocalFilesystemObjectStore
from kb_ingestion.infrastructure.object_store.minio_store import MinioObjectStore
from kb_ingestion.infrastructure.parsing.simple_html_section_parser import (
    SimpleHtmlSectionParser,
)
from kb_ingestion.infrastructure.persistence.in_memory import (
    InMemoryChunkRepository,
    InMemoryFilingRepository,
    InMemoryIngestionCursor,
    InMemoryObjectStore,
    InMemoryVectorStore,
)
from kb_ingestion.infrastructure.persistence.postgres_store import (
    PgVectorStore,
    PostgresFilingRepository,
    PostgresKnowledgeStore,
)
from kb_ingestion.infrastructure.persistence.sqlite_store import SqliteKnowledgeStore
from kb_ingestion.infrastructure.search.opensearch_index import OpenSearchChunkIndex


@dataclass(frozen=True, slots=True)
class IngestRuntime:
    use_case: IngestFiling
    edgar: HttpEdgarClient
    object_store: ObjectStorePort
    filings: FilingRepository
    embedder: EmbedderPort
    data_dir: Path | None = None
    knowledge_store: SqliteKnowledgeStore | None = None
    postgres_store: PostgresKnowledgeStore | None = None
    search_index: SearchIndexPort | None = None
    embedder_label: str = "hash"
    # Architecture §2 named views over `postgres_store` (compose only); thin
    # wrappers, not a second connection pool.
    filing_repository: PostgresFilingRepository | None = None
    vector_store: PgVectorStore | None = None


def build_openai_embedder(
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> OpenAIEmbedder:
    key = api_key if api_key is not None else require_openai_api_key()
    resolved_model = model or os.environ.get("OPENAI_EMBEDDING_MODEL", "").strip() or DEFAULT_MODEL
    return OpenAIEmbedder(
        api_key=key,
        model=resolved_model,
        dimensions=DEFAULT_DIMENSIONS,
        base_url=base_url,
    )


def build_local_ingest(
    *,
    user_agent: str,
    data_dir: Path,
    embedder: EmbedderPort | None = None,
    require_openai: bool = True,
    openai_api_key: str | None = None,
    openai_base_url: str | None = None,
    openai_embedding_model: str | None = None,
) -> IngestRuntime:
    """Filesystem + SQLite persistence; live SEC HTTP client."""
    data_dir.mkdir(parents=True, exist_ok=True)
    object_store = LocalFilesystemObjectStore(data_dir / "raw")
    db = SqliteKnowledgeStore(data_dir / "ingestion.sqlite3")
    edgar = HttpEdgarClient(user_agent)
    resolved = _resolve_embedder(
        embedder,
        require_openai=require_openai,
        openai_api_key=openai_api_key,
        openai_base_url=openai_base_url,
        openai_embedding_model=openai_embedding_model,
    )
    use_case = IngestFiling(
        edgar=edgar,
        store=object_store,
        filings=db,
        parser=SimpleHtmlSectionParser(),
        embedder=resolved.embedder,
        chunks=db,
        vectors=db,
        cursor=db,
    )
    return IngestRuntime(
        use_case=use_case,
        edgar=edgar,
        object_store=object_store,
        filings=db,
        embedder=resolved.embedder,
        data_dir=data_dir,
        knowledge_store=db,
        embedder_label=resolved.label,
    )


def build_memory_ingest(
    *,
    user_agent: str,
    embedder: EmbedderPort | None = None,
    require_openai: bool = True,
    openai_api_key: str | None = None,
    openai_base_url: str | None = None,
    openai_embedding_model: str | None = None,
) -> IngestRuntime:
    """In-memory persistence; live SEC HTTP client (useful for dry runs)."""
    edgar = HttpEdgarClient(user_agent)
    object_store = InMemoryObjectStore()
    filings = InMemoryFilingRepository()
    resolved = _resolve_embedder(
        embedder,
        require_openai=require_openai,
        openai_api_key=openai_api_key,
        openai_base_url=openai_base_url,
        openai_embedding_model=openai_embedding_model,
    )
    use_case = IngestFiling(
        edgar=edgar,
        store=object_store,
        filings=filings,
        parser=SimpleHtmlSectionParser(),
        embedder=resolved.embedder,
        chunks=InMemoryChunkRepository(),
        vectors=InMemoryVectorStore(),
        cursor=InMemoryIngestionCursor(),
    )
    return IngestRuntime(
        use_case=use_case,
        edgar=edgar,
        object_store=object_store,
        filings=filings,
        embedder=resolved.embedder,
        embedder_label=resolved.label,
    )


async def build_compose_ingest(
    *,
    user_agent: str,
    database_url: str | None = None,
    minio_endpoint: str | None = None,
    minio_access_key: str | None = None,
    minio_secret_key: str | None = None,
    minio_bucket: str | None = None,
    opensearch_url: str | None = None,
    opensearch_username: str | None = None,
    opensearch_password: str | None = None,
    embedder: EmbedderPort | None = None,
    require_openai: bool = True,
    openai_api_key: str | None = None,
    openai_base_url: str | None = None,
    openai_embedding_model: str | None = None,
) -> IngestRuntime:
    """MinIO + Postgres/pgvector + OpenSearch; live SEC HTTP client."""
    db_url = (database_url or os.environ.get("DATABASE_URL", "")).strip()
    if not db_url:
        raise ValueError("DATABASE_URL is required for compose ingest")
    endpoint = (minio_endpoint or os.environ.get("MINIO_ENDPOINT", "localhost:9000")).strip()
    access = (minio_access_key or os.environ.get("MINIO_ACCESS_KEY", "minioadmin")).strip()
    secret = (minio_secret_key or os.environ.get("MINIO_SECRET_KEY", "minioadmin")).strip()
    bucket = (minio_bucket or os.environ.get("MINIO_BUCKET", "kb-filings")).strip()
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

    object_store = MinioObjectStore(
        endpoint=endpoint,
        access_key=access,
        secret_key=secret,
        bucket=bucket,
    )
    db = await PostgresKnowledgeStore.connect(db_url)
    # OpenSearch is an optional add-on: compose only *requires* Postgres +
    # MinIO. Unset/unreachable OpenSearch skips BM25 indexing rather than
    # failing wiring (query then falls back to dense-only retrieval).
    search: OpenSearchChunkIndex | None
    try:
        search = OpenSearchChunkIndex(
            url=os_url,
            username=os_user or None,
            password=os_password or None,
        )
    except Exception:  # noqa: BLE001
        search = None
    edgar = HttpEdgarClient(user_agent)
    resolved = _resolve_embedder(
        embedder,
        require_openai=require_openai,
        openai_api_key=openai_api_key,
        openai_base_url=openai_base_url,
        openai_embedding_model=openai_embedding_model,
    )
    use_case = IngestFiling(
        edgar=edgar,
        store=object_store,
        filings=db,
        parser=SimpleHtmlSectionParser(),
        embedder=resolved.embedder,
        chunks=db,
        vectors=db,
        cursor=db,
        search_index=search,
    )
    return IngestRuntime(
        use_case=use_case,
        edgar=edgar,
        object_store=object_store,
        filings=db,
        embedder=resolved.embedder,
        postgres_store=db,
        search_index=search,
        embedder_label=resolved.label,
        filing_repository=PostgresFilingRepository(db),
        vector_store=PgVectorStore(db),
    )


@dataclass(frozen=True, slots=True)
class _ResolvedEmbedder:
    embedder: EmbedderPort
    label: str


def _resolve_embedder(
    embedder: EmbedderPort | None,
    *,
    require_openai: bool,
    openai_api_key: str | None = None,
    openai_base_url: str | None = None,
    openai_embedding_model: str | None = None,
) -> _ResolvedEmbedder:
    if embedder is not None:
        label = getattr(embedder, "model", None) or type(embedder).__name__
        return _ResolvedEmbedder(embedder=embedder, label=str(label))
    if require_openai:
        openai = build_openai_embedder(
            api_key=openai_api_key,
            model=openai_embedding_model,
            base_url=openai_base_url,
        )
        return _ResolvedEmbedder(embedder=openai, label=openai.model)
    return _ResolvedEmbedder(embedder=HashEmbedder(dimensions=32), label="hash")
