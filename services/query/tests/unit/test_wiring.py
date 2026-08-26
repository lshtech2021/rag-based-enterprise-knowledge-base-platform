from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from kb_domain import CIK, AccessionNumber, Chunk, Filing
from kb_ingestion.infrastructure.persistence.sqlite_store import SqliteKnowledgeStore
from kb_query.infrastructure.wiring import build_local_answer_query


@pytest.mark.asyncio
async def test_build_local_answer_query_loads_corpus(tmp_path: Path) -> None:
    data_dir = tmp_path / "ingestion"
    db = SqliteKnowledgeStore(data_dir / "ingestion.sqlite3")
    accn = AccessionNumber("0000320193-24-000123")
    chunk = Chunk(
        chunk_id=f"{accn}:0",
        accession_no=accn,
        section="Item 1A Risk Factors",
        text="Competition risks are material.",
        token_count=8,
    )
    await db.upsert_company(CIK("320193"), "Apple Inc.")
    await db.save_filing(
        Filing(
            accession_no=accn,
            cik=CIK("320193"),
            form_type="10-K",
            filed_date=date(2024, 11, 1),
            s3_raw_path="file:///tmp/a.htm",
        ),
        source_url="https://example.com/a.htm",
    )
    await db.replace_chunks(accn, [chunk])
    await db.upsert_embeddings([(chunk, [0.1, 0.2], {"source_url": "https://example.com/a.htm"})])

    runtime = await build_local_answer_query(data_dir=data_dir, openai_api_key="test-key")
    assert runtime.corpus_size == 1
    assert runtime.use_case is not None
    await runtime.embedder.aclose()
    await runtime.llm.aclose()
