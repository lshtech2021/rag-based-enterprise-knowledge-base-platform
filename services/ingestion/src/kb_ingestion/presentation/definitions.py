"""Dagster asset graph for EDGAR ingestion MVP."""

from __future__ import annotations

from typing import Any

from dagster import Definitions, graph, op
from kb_domain import CIK
from kb_ingestion.application.use_cases.ingest_filing import IngestFiling
from kb_ingestion.infrastructure.embeddings.hash_embedder import HashEmbedder
from kb_ingestion.infrastructure.parsing.simple_html_section_parser import SimpleHtmlSectionParser
from kb_ingestion.infrastructure.persistence.in_memory import (
    InMemoryChunkRepository,
    InMemoryFilingRepository,
    InMemoryIngestionCursor,
    InMemoryObjectStore,
    InMemoryVectorStore,
)


class StaticEdgar:
    """Resource-friendly stub edgar used when wiring the graph without live SEC."""

    def __init__(self, meta: Any, body: bytes) -> None:
        self._meta = meta
        self._body = body

    async def fetch_latest_filing(self, cik: CIK, form_types: tuple[str, ...] = ()) -> Any:
        return self._meta

    async def download_filing_document(self, meta: Any) -> bytes:
        return self._body


@op
def raw_filing(context) -> dict[str, str]:
    """Placeholder op: real runs inject CIK via config / sensors later."""
    cik = (context.op_config or {}).get("cik", "0000320193")
    return {"cik": cik}


@op
def parsed_doc(raw: dict[str, str]) -> dict[str, str]:
    return raw


@op
def chunks(doc: dict[str, str]) -> dict[str, str]:
    return doc


@op
def embeddings(chunk_state: dict[str, str]) -> dict[str, object]:
    """Terminal op documenting the pipeline order for the MVP graph."""
    return {"cik": chunk_state["cik"], "stage": "embeddings"}


@graph
def edgar_ingestion_graph() -> None:
    embeddings(chunks(parsed_doc(raw_filing())))


edgar_ingestion_job = edgar_ingestion_graph.to_job(name="edgar_ingestion_job")


def build_ingest_filing_with_fakes(edgar: Any) -> IngestFiling:
    return IngestFiling(
        edgar=edgar,
        store=InMemoryObjectStore(),
        filings=InMemoryFilingRepository(),
        parser=SimpleHtmlSectionParser(),
        embedder=HashEmbedder(dimensions=32),
        chunks=InMemoryChunkRepository(),
        vectors=InMemoryVectorStore(),
        cursor=InMemoryIngestionCursor(),
    )


defs = Definitions(jobs=[edgar_ingestion_job])
