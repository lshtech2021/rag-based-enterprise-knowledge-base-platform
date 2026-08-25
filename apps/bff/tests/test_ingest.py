from datetime import date

from fastapi.testclient import TestClient
from kb_bff.main import create_app
from kb_domain import CIK, AccessionNumber
from kb_ingestion.application.ports import EdgarFilingMeta
from kb_ingestion.application.use_cases.ingest_filing import IngestFiling
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


def _client() -> TestClient:
    store = InMemoryObjectStore()
    filings = InMemoryFilingRepository()
    use_case = IngestFiling(
        edgar=FakeEdgar(),
        store=store,
        filings=filings,
        parser=SimpleHtmlSectionParser(),
        embedder=HashEmbedder(dimensions=32),
        chunks=InMemoryChunkRepository(),
        vectors=InMemoryVectorStore(),
        cursor=InMemoryIngestionCursor(),
    )
    app = create_app()
    app.state.ingest_filing = use_case
    app.state.filing_repository = filings
    app.state.object_store = store
    return TestClient(app)


def test_ingest_and_download_raw() -> None:
    client = _client()
    created = client.post(
        "/v1/ingest",
        json={"cik": "320193", "form_types": ["10-K"], "force": True},
    )
    assert created.status_code == 200
    body = created.json()
    assert body["accession_no"] == "0000320193-24-000123"
    assert body["skipped"] is False
    assert body["chunk_count"] >= 1
    assert body["download_url"] == "/v1/filings/0000320193-24-000123/raw"

    raw = client.get(body["download_url"])
    assert raw.status_code == 200
    assert b"Risk Factors" in raw.content
    assert "attachment" in raw.headers.get("content-disposition", "")


def test_download_missing_filing_404() -> None:
    client = _client()
    assert client.get("/v1/filings/0000000000-00-000000/raw").status_code == 404
