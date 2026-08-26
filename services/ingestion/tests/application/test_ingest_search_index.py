from datetime import date

import pytest
from kb_domain import CIK, AccessionNumber
from kb_ingestion.application.ports import EdgarFilingMeta
from kb_ingestion.application.use_cases.ingest_filing import IngestFiling, IngestFilingCommand
from kb_ingestion.infrastructure.embeddings.hash_embedder import HashEmbedder
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

FIXTURE_HTML = b"""
<html><body>
<h1>Item 1A. Risk Factors</h1>
<p>We face substantial competition risks in consumer markets worldwide.</p>
</body></html>
"""


class FakeEdgar:
    def __init__(self) -> None:
        self.meta = EdgarFilingMeta(
            accession_no=AccessionNumber("0000320193-24-000123"),
            cik=CIK("320193"),
            form_type="10-K",
            filed_date=date(2024, 11, 1),
            primary_document="aapl.htm",
            company_name="Apple Inc.",
            source_url="https://www.sec.gov/Archives/example.htm",
        )

    async def fetch_latest_filing(
        self, cik: CIK, form_types: tuple[str, ...] = ()
    ) -> EdgarFilingMeta:
        return self.meta

    async def download_filing_document(self, meta: EdgarFilingMeta) -> bytes:
        return FIXTURE_HTML


class FakeSearchIndex:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, str]] = []

    async def replace_chunks(self, accession_no, chunks, *, source_url: str) -> None:  # noqa: ANN001
        self.calls.append((str(accession_no), len(chunks), source_url))

    async def search_bm25(self, query: str, *, top_k: int = 5):  # noqa: ANN001
        return []


@pytest.mark.asyncio
async def test_ingest_filing_updates_search_index() -> None:
    search = FakeSearchIndex()
    uc = IngestFiling(
        edgar=FakeEdgar(),
        store=InMemoryObjectStore(),
        filings=InMemoryFilingRepository(),
        parser=SimpleHtmlSectionParser(),
        embedder=HashEmbedder(dimensions=32),
        chunks=InMemoryChunkRepository(),
        vectors=InMemoryVectorStore(),
        cursor=InMemoryIngestionCursor(),
        search_index=search,
    )
    result = await uc.execute(IngestFilingCommand(cik=CIK("320193"), force=True))
    assert result.skipped is False
    assert search.calls
    assert search.calls[0][1] == result.chunk_count
