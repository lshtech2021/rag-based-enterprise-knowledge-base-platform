from datetime import date

import pytest
from kb_domain import CIK, AccessionNumber
from kb_ingestion.application.ports import EdgarFilingMeta
from kb_ingestion.application.use_cases.ingest_filing import IngestFiling, IngestFilingCommand
from kb_ingestion.infrastructure.embeddings.hash_embedder import HashEmbedder
from kb_ingestion.infrastructure.parsing.simple_html_section_parser import SimpleHtmlSectionParser
from kb_ingestion.infrastructure.persistence.in_memory import (
    InMemoryChunkRepository,
    InMemoryFilingRepository,
    InMemoryIngestionCursor,
    InMemoryObjectStore,
    InMemoryVectorStore,
)

FIXTURE_HTML = b"""
<html><body>
<h1>Item 1A. Risk Factors</h1>
<p>We face substantial risks related to market competition and regulation across segments.</p>
<h1>Item 7. Management's Discussion and Analysis</h1>
<p>Revenue increased year over year due to product demand and services growth.</p>
</body></html>
"""


class FakeEdgar:
    def __init__(self, meta: EdgarFilingMeta, body: bytes = FIXTURE_HTML) -> None:
        self.meta = meta
        self.body = body
        self.download_calls = 0

    async def fetch_latest_filing(
        self, cik: CIK, form_types: tuple[str, ...] = ("10-K", "10-Q", "8-K")
    ) -> EdgarFilingMeta:
        return self.meta

    async def download_filing_document(self, meta: EdgarFilingMeta) -> bytes:
        self.download_calls += 1
        return self.body


def _meta() -> EdgarFilingMeta:
    return EdgarFilingMeta(
        accession_no=AccessionNumber("0000320193-24-000123"),
        cik=CIK("320193"),
        form_type="10-K",
        filed_date=date(2024, 11, 1),
        primary_document="aapl-20240928.htm",
        company_name="Apple Inc.",
        source_url="https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl.htm",
    )


def _use_case(
    edgar: FakeEdgar,
) -> tuple[IngestFiling, InMemoryChunkRepository, InMemoryVectorStore]:
    chunks = InMemoryChunkRepository()
    vectors = InMemoryVectorStore()
    uc = IngestFiling(
        edgar=edgar,
        store=InMemoryObjectStore(),
        filings=InMemoryFilingRepository(),
        parser=SimpleHtmlSectionParser(),
        embedder=HashEmbedder(dimensions=32),
        chunks=chunks,
        vectors=vectors,
        cursor=InMemoryIngestionCursor(),
    )
    return uc, chunks, vectors


@pytest.mark.asyncio
async def test_ingest_filing_writes_chunks_and_embeddings() -> None:
    edgar = FakeEdgar(_meta())
    uc, chunks, vectors = _use_case(edgar)
    result = await uc.execute(IngestFilingCommand(cik=CIK("320193")))

    assert result.skipped is False
    assert result.chunk_count >= 1
    assert result.s3_raw_path is not None
    stored = await chunks.list_chunks(result.accession_no)
    assert stored
    assert any("Risk" in c.section for c in stored)
    assert await vectors.get_embedding(stored[0].chunk_id) is not None


@pytest.mark.asyncio
async def test_ingest_filing_skips_when_cursor_up_to_date() -> None:
    edgar = FakeEdgar(_meta())
    cursor = InMemoryIngestionCursor()
    await cursor.set_last_ingested(CIK("320193"), AccessionNumber("0000320193-24-000123"))
    uc = IngestFiling(
        edgar=edgar,
        store=InMemoryObjectStore(),
        filings=InMemoryFilingRepository(),
        parser=SimpleHtmlSectionParser(),
        embedder=HashEmbedder(dimensions=32),
        chunks=InMemoryChunkRepository(),
        vectors=InMemoryVectorStore(),
        cursor=cursor,
    )
    result = await uc.execute(IngestFilingCommand(cik=CIK("320193")))
    assert result.skipped is True
    assert edgar.download_calls == 0
