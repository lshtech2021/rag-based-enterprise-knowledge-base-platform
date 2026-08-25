"""In-memory adapters for ingestion application tests."""

from __future__ import annotations

from kb_application_ports import ObjectStorePort
from kb_domain import CIK, AccessionNumber, Chunk, Filing
from kb_ingestion.application.ports import (
    ChunkRepository,
    FilingRepository,
    IngestionCursorPort,
    VectorStorePort,
)


class InMemoryObjectStore:
    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    async def put_bytes(self, key: str, body: bytes, content_type: str) -> str:
        self._objects[key] = body
        return f"memory://{key}"

    async def get_bytes(self, key: str) -> bytes:
        return self._objects[key]


class InMemoryFilingRepository:
    def __init__(self) -> None:
        self.companies: dict[str, tuple[str, str | None]] = {}
        self.filings: dict[str, tuple[Filing, str]] = {}

    async def upsert_company(self, cik: CIK, name: str, ticker: str | None = None) -> None:
        self.companies[str(cik)] = (name, ticker)

    async def save_filing(self, filing: Filing, source_url: str) -> None:
        self.filings[str(filing.accession_no)] = (filing, source_url)

    async def get_filing(self, accession_no: AccessionNumber) -> Filing | None:
        row = self.filings.get(str(accession_no))
        return row[0] if row else None


class InMemoryChunkRepository:
    def __init__(self) -> None:
        self._by_accession: dict[str, list[Chunk]] = {}

    async def replace_chunks(self, accession_no: AccessionNumber, chunks: list[Chunk]) -> None:
        self._by_accession[str(accession_no)] = list(chunks)

    async def list_chunks(self, accession_no: AccessionNumber) -> list[Chunk]:
        return list(self._by_accession.get(str(accession_no), []))


class InMemoryVectorStore:
    def __init__(self) -> None:
        self.vectors: dict[str, list[float]] = {}
        self.metadata: dict[str, dict[str, object]] = {}

    async def upsert_embeddings(
        self, items: list[tuple[Chunk, list[float], dict[str, object]]]
    ) -> None:
        for chunk, vector, meta in items:
            self.vectors[chunk.chunk_id] = vector
            self.metadata[chunk.chunk_id] = meta

    async def get_embedding(self, chunk_id: str) -> list[float] | None:
        return self.vectors.get(chunk_id)


class InMemoryIngestionCursor:
    def __init__(self) -> None:
        self._last: dict[str, AccessionNumber] = {}

    async def get_last_ingested(self, cik: CIK) -> AccessionNumber | None:
        return self._last.get(str(cik))

    async def set_last_ingested(self, cik: CIK, accession_no: AccessionNumber) -> None:
        self._last[str(cik)] = accession_no


def as_object_store(store: InMemoryObjectStore) -> ObjectStorePort:
    return store


def as_filing_repo(repo: InMemoryFilingRepository) -> FilingRepository:
    return repo


def as_chunk_repo(repo: InMemoryChunkRepository) -> ChunkRepository:
    return repo


def as_vector_store(store: InMemoryVectorStore) -> VectorStorePort:
    return store


def as_cursor(cursor: InMemoryIngestionCursor) -> IngestionCursorPort:
    return cursor
