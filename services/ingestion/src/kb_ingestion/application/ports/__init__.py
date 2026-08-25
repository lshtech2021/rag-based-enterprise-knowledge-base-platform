"""Application outbound / inbound ports for ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

from kb_domain import CIK, AccessionNumber, Chunk, Filing


@dataclass(frozen=True, slots=True)
class EdgarFilingMeta:
    accession_no: AccessionNumber
    cik: CIK
    form_type: str
    filed_date: date
    primary_document: str
    company_name: str
    source_url: str


@dataclass(frozen=True, slots=True)
class ParsedSection:
    name: str
    text: str


@runtime_checkable
class EdgarPort(Protocol):
    async def fetch_latest_filing(
        self, cik: CIK, form_types: tuple[str, ...] = ("10-K", "10-Q", "8-K")
    ) -> EdgarFilingMeta:
        """Resolve latest matching filing metadata for a CIK."""
        ...

    async def download_filing_document(self, meta: EdgarFilingMeta) -> bytes:
        """Download raw primary document bytes."""
        ...


@runtime_checkable
class FilingRepository(Protocol):
    async def upsert_company(self, cik: CIK, name: str, ticker: str | None = None) -> None: ...

    async def save_filing(self, filing: Filing, source_url: str) -> None: ...

    async def get_filing(self, accession_no: AccessionNumber) -> Filing | None: ...


@runtime_checkable
class ChunkRepository(Protocol):
    async def replace_chunks(self, accession_no: AccessionNumber, chunks: list[Chunk]) -> None: ...

    async def list_chunks(self, accession_no: AccessionNumber) -> list[Chunk]: ...


@runtime_checkable
class VectorStorePort(Protocol):
    async def upsert_embeddings(
        self, items: list[tuple[Chunk, list[float], dict[str, object]]]
    ) -> None: ...

    async def get_embedding(self, chunk_id: str) -> list[float] | None: ...


@runtime_checkable
class EmbedderPort(Protocol):
    @property
    def dimensions(self) -> int: ...

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class DocumentParserPort(Protocol):
    def parse(self, raw_html: bytes) -> list[ParsedSection]: ...


@runtime_checkable
class IngestionCursorPort(Protocol):
    async def get_last_ingested(self, cik: CIK) -> AccessionNumber | None: ...

    async def set_last_ingested(self, cik: CIK, accession_no: AccessionNumber) -> None: ...
