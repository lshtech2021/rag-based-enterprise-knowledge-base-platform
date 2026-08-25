"""Build a fully wired IngestFiling for local or in-memory backends."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from kb_application_ports import ObjectStorePort
from kb_ingestion.application.ports import EmbedderPort, FilingRepository
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
from kb_ingestion.infrastructure.persistence.sqlite_store import SqliteKnowledgeStore


@dataclass(frozen=True, slots=True)
class IngestRuntime:
    use_case: IngestFiling
    edgar: HttpEdgarClient
    object_store: ObjectStorePort
    filings: FilingRepository
    embedder: EmbedderPort
    data_dir: Path | None = None
    knowledge_store: SqliteKnowledgeStore | None = None
    embedder_label: str = "hash"


def build_openai_embedder(
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> OpenAIEmbedder:
    key = api_key if api_key is not None else require_openai_api_key()
    resolved_model = model or os.environ.get("OPENAI_EMBEDDING_MODEL", "").strip() or DEFAULT_MODEL
    return OpenAIEmbedder(api_key=key, model=resolved_model, dimensions=DEFAULT_DIMENSIONS)


def build_local_ingest(
    *,
    user_agent: str,
    data_dir: Path,
    embedder: EmbedderPort | None = None,
    require_openai: bool = True,
) -> IngestRuntime:
    """Filesystem + SQLite persistence; live SEC HTTP client."""
    data_dir.mkdir(parents=True, exist_ok=True)
    object_store = LocalFilesystemObjectStore(data_dir / "raw")
    db = SqliteKnowledgeStore(data_dir / "ingestion.sqlite3")
    edgar = HttpEdgarClient(user_agent)
    resolved = _resolve_embedder(embedder, require_openai=require_openai)
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
) -> IngestRuntime:
    """In-memory persistence; live SEC HTTP client (useful for dry runs)."""
    edgar = HttpEdgarClient(user_agent)
    object_store = InMemoryObjectStore()
    filings = InMemoryFilingRepository()
    resolved = _resolve_embedder(embedder, require_openai=require_openai)
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


@dataclass(frozen=True, slots=True)
class _ResolvedEmbedder:
    embedder: EmbedderPort
    label: str


def _resolve_embedder(
    embedder: EmbedderPort | None,
    *,
    require_openai: bool,
) -> _ResolvedEmbedder:
    if embedder is not None:
        label = getattr(embedder, "model", None) or type(embedder).__name__
        return _ResolvedEmbedder(embedder=embedder, label=str(label))
    if require_openai:
        openai = build_openai_embedder()
        return _ResolvedEmbedder(embedder=openai, label=openai.model)
    return _ResolvedEmbedder(embedder=HashEmbedder(dimensions=32), label="hash")
