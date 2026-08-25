"""SQLite-backed repositories for local EDGAR ingestion."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from kb_domain import CIK, AccessionNumber, Chunk, Filing


class SqliteKnowledgeStore:
    """Implements filing/chunk/vector/cursor ports against one SQLite file."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        schema = (
            Path(__file__).resolve().parents[1] / "schema" / "001_ingestion_sqlite.sql"
        ).read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(schema)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    async def upsert_company(self, cik: CIK, name: str, ticker: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO companies (cik, name, ticker)
                VALUES (?, ?, ?)
                ON CONFLICT(cik) DO UPDATE SET
                    name = excluded.name,
                    ticker = COALESCE(excluded.ticker, companies.ticker)
                """,
                (str(cik), name, ticker),
            )
            conn.commit()

    async def save_filing(self, filing: Filing, source_url: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO filings (
                    accession_no, cik, form_type, filed_date, period, s3_raw_path, source_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(accession_no) DO UPDATE SET
                    cik = excluded.cik,
                    form_type = excluded.form_type,
                    filed_date = excluded.filed_date,
                    period = excluded.period,
                    s3_raw_path = excluded.s3_raw_path,
                    source_url = excluded.source_url
                """,
                (
                    str(filing.accession_no),
                    str(filing.cik),
                    filing.form_type,
                    filing.filed_date.isoformat(),
                    filing.period,
                    filing.s3_raw_path or "",
                    source_url,
                ),
            )
            conn.commit()

    async def get_filing(self, accession_no: AccessionNumber) -> Filing | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM filings WHERE accession_no = ?",
                (str(accession_no),),
            ).fetchone()
        if row is None:
            return None
        return Filing(
            accession_no=AccessionNumber(row["accession_no"]),
            cik=CIK(row["cik"]),
            form_type=row["form_type"],
            filed_date=date.fromisoformat(row["filed_date"]),
            period=row["period"],
            s3_raw_path=row["s3_raw_path"],
        )

    async def replace_chunks(self, accession_no: AccessionNumber, chunks: list[Chunk]) -> None:
        accn = str(accession_no)
        with self._connect() as conn:
            conn.execute(
                """
                DELETE FROM embeddings
                WHERE chunk_id IN (
                    SELECT chunk_id FROM chunks WHERE accession_no = ?
                )
                """,
                (accn,),
            )
            conn.execute("DELETE FROM chunks WHERE accession_no = ?", (accn,))
            for index, chunk in enumerate(chunks):
                conn.execute(
                    """
                    INSERT INTO chunks (
                        chunk_id, accession_no, section, text, token_count, chunk_index
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.chunk_id,
                        str(chunk.accession_no),
                        chunk.section,
                        chunk.text,
                        chunk.token_count,
                        index,
                    ),
                )
            conn.commit()

    async def list_chunks(self, accession_no: AccessionNumber) -> list[Chunk]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT chunk_id, accession_no, section, text, token_count
                FROM chunks
                WHERE accession_no = ?
                ORDER BY chunk_index
                """,
                (str(accession_no),),
            ).fetchall()
        return [
            Chunk(
                chunk_id=row["chunk_id"],
                accession_no=AccessionNumber(row["accession_no"]),
                section=row["section"],
                text=row["text"],
                token_count=row["token_count"],
            )
            for row in rows
        ]

    async def upsert_embeddings(
        self, items: list[tuple[Chunk, list[float], dict[str, object]]]
    ) -> None:
        with self._connect() as conn:
            for chunk, vector, meta in items:
                conn.execute(
                    """
                    INSERT INTO embeddings (chunk_id, embedding_json, metadata_json)
                    VALUES (?, ?, ?)
                    ON CONFLICT(chunk_id) DO UPDATE SET
                        embedding_json = excluded.embedding_json,
                        metadata_json = excluded.metadata_json
                    """,
                    (chunk.chunk_id, json.dumps(vector), json.dumps(meta)),
                )
            conn.commit()

    async def get_embedding(self, chunk_id: str) -> list[float] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT embedding_json FROM embeddings WHERE chunk_id = ?",
                (chunk_id,),
            ).fetchone()
        if row is None:
            return None
        return list(json.loads(row["embedding_json"]))

    async def get_last_ingested(self, cik: CIK) -> AccessionNumber | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT last_ingested_accession FROM companies WHERE cik = ?",
                (str(cik),),
            ).fetchone()
        if row is None or row["last_ingested_accession"] is None:
            return None
        return AccessionNumber(row["last_ingested_accession"])

    async def set_last_ingested(self, cik: CIK, accession_no: AccessionNumber) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE companies
                SET last_ingested_accession = ?
                WHERE cik = ?
                """,
                (str(accession_no), str(cik)),
            )
            conn.commit()
