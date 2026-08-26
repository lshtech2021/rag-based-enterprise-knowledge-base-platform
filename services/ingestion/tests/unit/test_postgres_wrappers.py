"""Architecture §2 naming: PostgresFilingRepository / PgVectorStore delegate

to a shared PostgresKnowledgeStore-like object without a second connection
pool. Verified here with a fake (no live Postgres needed).
"""

from __future__ import annotations

from datetime import date

import pytest
from kb_domain import CIK, AccessionNumber, Chunk, Filing
from kb_ingestion.infrastructure.persistence.postgres_store import (
    PgVectorStore,
    PostgresFilingRepository,
)


class _FakeStore:
    def __init__(self) -> None:
        self.companies: list[tuple[str, str, str | None]] = []
        self.filings: dict[str, Filing] = {}
        self.cursor: dict[str, str] = {}
        self.embeddings: list[tuple[Chunk, list[float], dict[str, object]]] = []

    async def upsert_company(self, cik: CIK, name: str, ticker: str | None = None) -> None:
        self.companies.append((str(cik), name, ticker))

    async def save_filing(self, filing: Filing, source_url: str) -> None:
        self.filings[str(filing.accession_no)] = filing

    async def get_filing(self, accession_no: AccessionNumber) -> Filing | None:
        return self.filings.get(str(accession_no))

    async def get_last_ingested(self, cik: CIK) -> AccessionNumber | None:
        raw = self.cursor.get(str(cik))
        return AccessionNumber(raw) if raw else None

    async def set_last_ingested(self, cik: CIK, accession_no: AccessionNumber) -> None:
        self.cursor[str(cik)] = str(accession_no)

    async def upsert_embeddings(
        self, items: list[tuple[Chunk, list[float], dict[str, object]]]
    ) -> None:
        self.embeddings.extend(items)

    async def get_embedding(self, chunk_id: str) -> list[float] | None:
        for chunk, vector, _meta in self.embeddings:
            if chunk.chunk_id == chunk_id:
                return vector
        return None

    async def search_dense(
        self, query_vector: list[float], *, top_k: int = 5
    ) -> list[tuple[Chunk, float, str]]:
        return [(chunk, 0.9, "https://example.com") for chunk, _vector, _meta in self.embeddings][
            :top_k
        ]


@pytest.mark.asyncio
async def test_postgres_filing_repository_delegates() -> None:
    fake = _FakeStore()
    repo = PostgresFilingRepository(fake)

    await repo.upsert_company(CIK("320193"), "Apple Inc.", "AAPL")
    filing = Filing(
        accession_no=AccessionNumber("0000320193-24-000123"),
        cik=CIK("320193"),
        form_type="10-K",
        filed_date=date(2024, 11, 1),
        s3_raw_path="s3://bucket/key",
    )
    await repo.save_filing(filing, source_url="https://example.com")

    assert fake.companies == [("0000320193", "Apple Inc.", "AAPL")]
    assert await repo.get_filing(filing.accession_no) == filing

    await repo.set_last_ingested(CIK("320193"), filing.accession_no)
    assert await repo.get_last_ingested(CIK("320193")) == filing.accession_no


@pytest.mark.asyncio
async def test_pg_vector_store_delegates() -> None:
    fake = _FakeStore()
    store = PgVectorStore(fake)

    chunk = Chunk(
        chunk_id="c1",
        accession_no=AccessionNumber("0000320193-24-000123"),
        section="Item 1A",
        text="risk text",
        token_count=10,
    )
    await store.upsert_embeddings([(chunk, [0.1, 0.2], {"section": "Item 1A"})])

    assert await store.get_embedding("c1") == [0.1, 0.2]
    hits = await store.search_dense([0.1, 0.2], top_k=5)
    assert hits[0][0].chunk_id == "c1"
