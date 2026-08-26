from datetime import date

import pytest
from kb_domain import CIK, AccessionNumber, Chunk, Filing
from kb_ingestion.infrastructure.object_store.local_fs import LocalFilesystemObjectStore
from kb_ingestion.infrastructure.persistence.sqlite_store import SqliteKnowledgeStore


@pytest.mark.asyncio
async def test_local_fs_object_store_roundtrip(tmp_path) -> None:
    store = LocalFilesystemObjectStore(tmp_path / "raw")
    uri = await store.put_bytes("filings/a.htm", b"<html>hi</html>", "text/html")
    assert uri.startswith("file://")
    assert await store.get_bytes("filings/a.htm") == b"<html>hi</html>"


@pytest.mark.asyncio
async def test_local_fs_rejects_path_escape(tmp_path) -> None:
    store = LocalFilesystemObjectStore(tmp_path / "raw")
    with pytest.raises(ValueError):
        await store.put_bytes("../escape.txt", b"x", "text/plain")


@pytest.mark.asyncio
async def test_sqlite_store_filing_chunks_embeddings_cursor(tmp_path) -> None:
    db = SqliteKnowledgeStore(tmp_path / "ingest.sqlite3")
    cik = CIK("320193")
    accn = AccessionNumber("0000320193-24-000123")
    await db.upsert_company(cik, "Apple Inc.", ticker="AAPL")
    await db.save_filing(
        Filing(
            accession_no=accn,
            cik=cik,
            form_type="10-K",
            filed_date=date(2024, 11, 1),
            s3_raw_path="file:///tmp/a.htm",
        ),
        source_url="https://example.com/a.htm",
    )
    chunk = Chunk(
        chunk_id=f"{accn}:0",
        accession_no=accn,
        section="Item 1A Risk Factors",
        text="Competition risks are material.",
        token_count=8,
    )
    await db.replace_chunks(accn, [chunk])
    await db.upsert_embeddings(
        [
            (
                chunk,
                [0.1, 0.2, 0.3],
                {"section": chunk.section, "source_url": "https://example.com/a.htm"},
            )
        ]
    )
    await db.set_last_ingested(cik, accn)

    assert await db.get_filing(accn) is not None
    assert (await db.list_chunks(accn))[0].chunk_id == chunk.chunk_id
    assert await db.get_embedding(chunk.chunk_id) == [0.1, 0.2, 0.3]
    assert await db.get_last_ingested(cik) == accn

    corpus = await db.list_retrieval_corpus()
    assert len(corpus) == 1
    loaded_chunk, vector, url = corpus[0]
    assert loaded_chunk.chunk_id == chunk.chunk_id
    assert vector == [0.1, 0.2, 0.3]
    assert url == "https://example.com/a.htm"
    assert await db.corpus_chunk_count() == 1
