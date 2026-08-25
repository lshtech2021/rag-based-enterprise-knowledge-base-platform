from datetime import date

import pytest
from kb_domain import CIK, AccessionNumber
from kb_ingestion.application.ports import EdgarFilingMeta
from kb_ingestion.application.use_cases.ingest_filing import IngestFiling, IngestFilingCommand
from kb_ingestion.infrastructure.embeddings.hash_embedder import HashEmbedder
from kb_ingestion.infrastructure.object_store.local_fs import LocalFilesystemObjectStore
from kb_ingestion.infrastructure.parsing.simple_html_section_parser import (
    SimpleHtmlSectionParser,
)
from kb_ingestion.infrastructure.persistence.sqlite_store import SqliteKnowledgeStore

FIXTURE_HTML = b"""
<html><body>
<h1>Item 1A. Risk Factors</h1>
<p>We face substantial competition risks in consumer markets worldwide.</p>
<h1>Item 7. Management's Discussion and Analysis</h1>
<p>Revenue increased year over year due to product demand and services growth.</p>
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


@pytest.mark.asyncio
async def test_ingest_filing_persists_to_local_backend(tmp_path) -> None:
    store = LocalFilesystemObjectStore(tmp_path / "raw")
    db = SqliteKnowledgeStore(tmp_path / "ingestion.sqlite3")
    uc = IngestFiling(
        edgar=FakeEdgar(),
        store=store,
        filings=db,
        parser=SimpleHtmlSectionParser(),
        embedder=HashEmbedder(dimensions=32),
        chunks=db,
        vectors=db,
        cursor=db,
    )
    result = await uc.execute(IngestFilingCommand(cik=CIK("320193")))
    assert result.skipped is False
    assert result.chunk_count >= 1
    assert result.s3_raw_path is not None
    assert await db.get_filing(result.accession_no) is not None
    chunks = await db.list_chunks(result.accession_no)
    assert chunks
    assert await db.get_embedding(chunks[0].chunk_id) is not None
    assert await db.get_last_ingested(CIK("320193")) == result.accession_no
