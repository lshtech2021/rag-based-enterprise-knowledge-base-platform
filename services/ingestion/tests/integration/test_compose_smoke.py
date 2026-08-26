"""Optional Compose integration tests — skipped unless KB_RUN_COMPOSE_TESTS=1."""

from __future__ import annotations

import os
from datetime import date

import pytest

pytestmark = pytest.mark.integration


def _enabled() -> bool:
    return os.environ.get("KB_RUN_COMPOSE_TESTS", "").strip() == "1"


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://kb:kb@localhost:5432/knowledge_base")


@pytest.mark.asyncio
@pytest.mark.skipif(not _enabled(), reason="Set KB_RUN_COMPOSE_TESTS=1 with Compose up")
async def test_compose_postgres_ping() -> None:
    from kb_ingestion.infrastructure.persistence.postgres_store import PostgresKnowledgeStore

    store = await PostgresKnowledgeStore.connect(_database_url())
    try:
        assert await store.ping() is True
    finally:
        await store.aclose()


@pytest.mark.asyncio
@pytest.mark.skipif(not _enabled(), reason="Set KB_RUN_COMPOSE_TESTS=1 with Compose up")
async def test_compose_ingest_writes_postgres_and_pgvector() -> None:
    """Full §7 fidelity check: ingest → companies/filings/chunks/embeddings rows,
    then a dense search against pgvector finds the ingested chunk."""
    from kb_domain import CIK, AccessionNumber
    from kb_ingestion.application.ports import EdgarFilingMeta
    from kb_ingestion.application.use_cases.ingest_filing import (
        IngestFiling,
        IngestFilingCommand,
    )
    from kb_ingestion.infrastructure.embeddings.hash_embedder import HashEmbedder
    from kb_ingestion.infrastructure.parsing.simple_html_section_parser import (
        SimpleHtmlSectionParser,
    )
    from kb_ingestion.infrastructure.persistence.in_memory import InMemoryObjectStore
    from kb_ingestion.infrastructure.persistence.postgres_store import PostgresKnowledgeStore

    fixture_html = (
        b"<html><body><h1>Item 1A. Risk Factors</h1>"
        b"<p>We face substantial competition risks in consumer markets worldwide.</p>"
        b"</body></html>"
    )

    class FakeEdgar:
        def __init__(self) -> None:
            self.meta = EdgarFilingMeta(
                accession_no=AccessionNumber("0000320193-24-000199"),
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
            return fixture_html

    db = await PostgresKnowledgeStore.connect(_database_url())
    try:
        embedder = HashEmbedder(dimensions=1536)
        use_case = IngestFiling(
            edgar=FakeEdgar(),
            store=InMemoryObjectStore(),
            filings=db,
            parser=SimpleHtmlSectionParser(),
            embedder=embedder,
            chunks=db,
            vectors=db,
            cursor=db,
        )
        result = await use_case.execute(IngestFilingCommand(cik=CIK("320193"), force=True))
        assert result.skipped is False
        assert result.chunk_count == 1
        assert await db.corpus_chunk_count() >= 1

        vector = (await embedder.embed_documents(["competition risks"]))[0]
        hits = await db.search_dense(vector, top_k=3)
        assert any(chunk.chunk_id == "0000320193-24-000199:0" for chunk, _score, _url in hits)
    finally:
        async with db._pool.connection() as conn:  # noqa: SLF001 - test cleanup only
            await conn.execute(
                "DELETE FROM embeddings WHERE chunk_id LIKE '0000320193-24-000199%'"
            )
            await conn.execute("DELETE FROM chunks WHERE accession_no = '0000320193-24-000199'")
            await conn.execute("DELETE FROM filings WHERE accession_no = '0000320193-24-000199'")
            await conn.execute("DELETE FROM companies WHERE cik = '0000320193'")
            await conn.commit()
        await db.aclose()


@pytest.mark.asyncio
@pytest.mark.skipif(not _enabled(), reason="Set KB_RUN_COMPOSE_TESTS=1 with Compose up")
async def test_compose_query_log_round_trip() -> None:
    from kb_domain import AccessionNumber, Citation
    from kb_ingestion.infrastructure.persistence.postgres_store import PostgresKnowledgeStore

    db = await PostgresKnowledgeStore.connect(_database_url())
    try:
        cite = Citation(
            chunk_id="c1",
            accession_no=AccessionNumber("0000320193-24-000123"),
            section="Item 1A",
            source_url="https://example.com",
        )
        await db.save(
            question="What are the risks?",
            answer="Some risks [cite:c1]",
            citations=[cite],
            retrieved_chunk_ids=["c1"],
            user_id="test-user",
            latency_ms=12.5,
        )
        async with db._pool.connection() as conn:  # noqa: SLF001 - test verification only
            cur = await conn.execute(
                "SELECT user_id, question FROM query_logs WHERE user_id = %s",
                ("test-user",),
            )
            rows = await cur.fetchall()
            assert any(row["question"] == "What are the risks?" for row in rows)
            await conn.execute("DELETE FROM query_logs WHERE user_id = %s", ("test-user",))
            await conn.commit()
    finally:
        await db.aclose()


@pytest.mark.asyncio
@pytest.mark.skipif(not _enabled(), reason="Set KB_RUN_COMPOSE_TESTS=1 with Compose up")
async def test_compose_report_repository_round_trip() -> None:
    from kb_domain import AccessionNumber, Citation
    from kb_report.application.ports import ReportSectionResult, StoredReport
    from kb_report.infrastructure.postgres_report_store import PostgresReportRepository

    repo = await PostgresReportRepository.connect(_database_url())
    try:
        cite = Citation(
            chunk_id="c1",
            accession_no=AccessionNumber("0000320193-24-000123"),
            section="Item 1A",
            source_url="https://example.com",
        )
        report = StoredReport(
            report_id="integration-test-report",
            user_id="test-user",
            template_id="quarterly_risk_summary",
            title="Quarterly Risk Summary",
            company="Apple Inc.",
            period="FY2024",
            markdown="# hi",
            sections=(
                ReportSectionResult(
                    section_id="risk_factors",
                    title="Key Risk Factors",
                    question="q?",
                    body="body text",
                    citations=(cite,),
                ),
            ),
        )
        await repo.save(report)
        fetched = await repo.get("integration-test-report")
        assert fetched is not None
        assert fetched.company == "Apple Inc."
        assert fetched.period == "FY2024"
        assert len(fetched.sections) == 1
        assert len(fetched.sections[0].citations) == 1
        assert await repo.ping() is True
    finally:
        async with repo._pool.connection() as conn:  # noqa: SLF001 - test cleanup only
            await conn.execute(
                "DELETE FROM report_citations WHERE report_id = %s",
                ("integration-test-report",),
            )
            await conn.execute(
                "DELETE FROM reports WHERE report_id = %s", ("integration-test-report",)
            )
            await conn.commit()
        await repo.aclose()
