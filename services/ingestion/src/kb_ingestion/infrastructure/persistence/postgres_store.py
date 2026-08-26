"""Postgres + pgvector knowledge store for compose data plane."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, cast
from uuid import uuid4

from kb_domain import CIK, AccessionNumber, Chunk, Citation, Filing
from pgvector.psycopg import register_vector_async
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

# Architecture §7 tables owned by the ingestion service. Applied on every
# `connect()` (idempotent) so any Postgres — not only a fresh Compose volume
# seeded by infra/initdb/ — ends up with the full schema.
_SCHEMA_STATEMENTS: tuple[str, ...] = (
    "CREATE EXTENSION IF NOT EXISTS vector",
    """
    CREATE TABLE IF NOT EXISTS companies (
        cik VARCHAR(10) PRIMARY KEY,
        name TEXT NOT NULL,
        ticker TEXT,
        sic TEXT,
        last_ingested_accession VARCHAR(20)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS filings (
        accession_no VARCHAR(20) PRIMARY KEY,
        cik VARCHAR(10) NOT NULL REFERENCES companies (cik),
        form_type TEXT NOT NULL,
        filed_date DATE NOT NULL,
        period TEXT,
        s3_raw_path TEXT NOT NULL,
        source_url TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chunks (
        chunk_id TEXT PRIMARY KEY,
        accession_no VARCHAR(20) NOT NULL REFERENCES filings (accession_no),
        section TEXT NOT NULL,
        text TEXT NOT NULL,
        token_count INTEGER NOT NULL,
        chunk_index INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS embeddings (
        chunk_id TEXT PRIMARY KEY REFERENCES chunks (chunk_id) ON DELETE CASCADE,
        embedding vector(1536) NOT NULL,
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb
    )
    """,
    # XBRL companyfacts land here once a loader exists (SPEC-ingestion); the
    # table is created up-front so query-side tooling can rely on it existing.
    """
    CREATE TABLE IF NOT EXISTS financial_facts (
        cik VARCHAR(10) NOT NULL REFERENCES companies (cik),
        concept TEXT NOT NULL,
        unit TEXT NOT NULL,
        value NUMERIC NOT NULL,
        fiscal_period TEXT NOT NULL,
        accession_no VARCHAR(20) NOT NULL REFERENCES filings (accession_no),
        PRIMARY KEY (cik, concept, unit, fiscal_period, accession_no)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS query_logs (
        query_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        question TEXT NOT NULL,
        retrieved_chunks JSONB NOT NULL DEFAULT '[]'::jsonb,
        answer TEXT NOT NULL,
        latency_ms DOUBLE PRECISION NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS filings_cik_idx ON filings (cik)",
    "CREATE INDEX IF NOT EXISTS chunks_accession_idx ON chunks (accession_no)",
    (
        "CREATE INDEX IF NOT EXISTS embeddings_hnsw_idx "
        "ON embeddings USING hnsw (embedding vector_cosine_ops)"
    ),
    "CREATE INDEX IF NOT EXISTS financial_facts_cik_idx ON financial_facts (cik)",
    "CREATE INDEX IF NOT EXISTS query_logs_user_idx ON query_logs (user_id)",
)


async def _ensure_schema(database_url: str) -> None:
    """Apply the ingestion schema against any reachable Postgres, idempotently.

    Runs outside the pooled connection (and before pgvector's async adapter is
    registered) because `CREATE EXTENSION vector` must exist before the
    ``pgvector`` type OID can be resolved.
    """
    conn = await AsyncConnection.connect(database_url)
    try:
        for statement in _SCHEMA_STATEMENTS:
            await conn.execute(statement)
        await conn.commit()
    finally:
        await conn.close()


async def _configure(conn: AsyncConnection[Any]) -> None:
    await register_vector_async(conn)


class PostgresKnowledgeStore:
    """Filing/chunk/vector/cursor ports against Postgres + pgvector."""

    def __init__(self, pool: AsyncConnectionPool[Any]) -> None:
        self._pool = pool

    @classmethod
    async def connect(
        cls,
        database_url: str,
        *,
        min_size: int = 1,
        max_size: int = 4,
        ensure_schema: bool = True,
    ) -> PostgresKnowledgeStore:
        if ensure_schema:
            await _ensure_schema(database_url)
        pool: AsyncConnectionPool[Any] = AsyncConnectionPool(
            conninfo=database_url,
            min_size=min_size,
            max_size=max_size,
            kwargs={"row_factory": dict_row},
            configure=_configure,
            open=False,
        )
        await pool.open()
        return cls(pool)

    async def aclose(self) -> None:
        await self._pool.close()

    async def upsert_company(self, cik: CIK, name: str, ticker: str | None = None) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO companies (cik, name, ticker)
                VALUES (%s, %s, %s)
                ON CONFLICT (cik) DO UPDATE SET
                    name = EXCLUDED.name,
                    ticker = COALESCE(EXCLUDED.ticker, companies.ticker)
                """,
                (str(cik), name, ticker),
            )
            await conn.commit()

    async def save_filing(self, filing: Filing, source_url: str) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO filings (
                    accession_no, cik, form_type, filed_date, period, s3_raw_path, source_url
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (accession_no) DO UPDATE SET
                    cik = EXCLUDED.cik,
                    form_type = EXCLUDED.form_type,
                    filed_date = EXCLUDED.filed_date,
                    period = EXCLUDED.period,
                    s3_raw_path = EXCLUDED.s3_raw_path,
                    source_url = EXCLUDED.source_url
                """,
                (
                    str(filing.accession_no),
                    str(filing.cik),
                    filing.form_type,
                    filing.filed_date,
                    filing.period,
                    filing.s3_raw_path or "",
                    source_url,
                ),
            )
            await conn.commit()

    async def get_filing(self, accession_no: AccessionNumber) -> Filing | None:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT * FROM filings WHERE accession_no = %s",
                (str(accession_no),),
            )
            data = cast(dict[str, Any] | None, await cur.fetchone())
        if data is None:
            return None
        filed = data["filed_date"]
        filed_date = filed if isinstance(filed, date) else date.fromisoformat(str(filed))
        return Filing(
            accession_no=AccessionNumber(data["accession_no"]),
            cik=CIK(data["cik"]),
            form_type=data["form_type"],
            filed_date=filed_date,
            period=data["period"],
            s3_raw_path=data["s3_raw_path"],
        )

    async def replace_chunks(self, accession_no: AccessionNumber, chunks: list[Chunk]) -> None:
        accn = str(accession_no)
        async with self._pool.connection() as conn:
            await conn.execute(
                """
                DELETE FROM embeddings
                WHERE chunk_id IN (
                    SELECT chunk_id FROM chunks WHERE accession_no = %s
                )
                """,
                (accn,),
            )
            await conn.execute("DELETE FROM chunks WHERE accession_no = %s", (accn,))
            for index, chunk in enumerate(chunks):
                await conn.execute(
                    """
                    INSERT INTO chunks (
                        chunk_id, accession_no, section, text, token_count, chunk_index
                    ) VALUES (%s, %s, %s, %s, %s, %s)
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
            await conn.commit()

    async def list_chunks(self, accession_no: AccessionNumber) -> list[Chunk]:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                """
                SELECT chunk_id, accession_no, section, text, token_count
                FROM chunks
                WHERE accession_no = %s
                ORDER BY chunk_index
                """,
                (str(accession_no),),
            )
            rows = cast(list[dict[str, Any]], await cur.fetchall())
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
        async with self._pool.connection() as conn:
            for chunk, vector, meta in items:
                await conn.execute(
                    """
                    INSERT INTO embeddings (chunk_id, embedding, metadata)
                    VALUES (%s, %s, %s::jsonb)
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata
                    """,
                    (chunk.chunk_id, vector, json.dumps(meta)),
                )
            await conn.commit()

    async def get_embedding(self, chunk_id: str) -> list[float] | None:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT embedding FROM embeddings WHERE chunk_id = %s",
                (chunk_id,),
            )
            row = cast(dict[str, Any] | None, await cur.fetchone())
        if row is None:
            return None
        return list(row["embedding"])

    async def get_last_ingested(self, cik: CIK) -> AccessionNumber | None:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT last_ingested_accession FROM companies WHERE cik = %s",
                (str(cik),),
            )
            row = cast(dict[str, Any] | None, await cur.fetchone())
        if row is None or row["last_ingested_accession"] is None:
            return None
        return AccessionNumber(row["last_ingested_accession"])

    async def set_last_ingested(self, cik: CIK, accession_no: AccessionNumber) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                """
                UPDATE companies
                SET last_ingested_accession = %s
                WHERE cik = %s
                """,
                (str(accession_no), str(cik)),
            )
            await conn.commit()

    async def list_retrieval_corpus(self) -> list[tuple[Chunk, list[float], str]]:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                """
                SELECT
                    c.chunk_id,
                    c.accession_no,
                    c.section,
                    c.text,
                    c.token_count,
                    e.embedding,
                    e.metadata,
                    COALESCE(f.source_url, '') AS source_url
                FROM chunks c
                INNER JOIN embeddings e ON e.chunk_id = c.chunk_id
                LEFT JOIN filings f ON f.accession_no = c.accession_no
                ORDER BY c.accession_no, c.chunk_index
                """
            )
            rows = cast(list[dict[str, Any]], await cur.fetchall())
        corpus: list[tuple[Chunk, list[float], str]] = []
        for row in rows:
            meta = row["metadata"] or {}
            if isinstance(meta, str):
                meta = json.loads(meta)
            source_url = row["source_url"] or str(meta.get("source_url") or "")
            corpus.append(
                (
                    Chunk(
                        chunk_id=row["chunk_id"],
                        accession_no=AccessionNumber(row["accession_no"]),
                        section=row["section"],
                        text=row["text"],
                        token_count=row["token_count"],
                    ),
                    list(row["embedding"]),
                    source_url,
                )
            )
        return corpus

    async def corpus_chunk_count(self) -> int:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                """
                SELECT COUNT(*) AS n
                FROM chunks c
                INNER JOIN embeddings e ON e.chunk_id = c.chunk_id
                """
            )
            row = cast(dict[str, Any] | None, await cur.fetchone())
        return int(row["n"]) if row is not None else 0

    async def search_dense(
        self, query_vector: list[float], *, top_k: int = 5
    ) -> list[tuple[Chunk, float, str]]:
        """Cosine-distance nearest neighbors → (chunk, score, source_url)."""
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                """
                SELECT
                    c.chunk_id,
                    c.accession_no,
                    c.section,
                    c.text,
                    c.token_count,
                    COALESCE(f.source_url, '') AS source_url,
                    1 - (e.embedding <=> %s::vector) AS score
                FROM embeddings e
                INNER JOIN chunks c ON c.chunk_id = e.chunk_id
                LEFT JOIN filings f ON f.accession_no = c.accession_no
                ORDER BY e.embedding <=> %s::vector
                LIMIT %s
                """,
                (query_vector, query_vector, top_k),
            )
            rows = cast(list[dict[str, Any]], await cur.fetchall())
        return [
            (
                Chunk(
                    chunk_id=row["chunk_id"],
                    accession_no=AccessionNumber(row["accession_no"]),
                    section=row["section"],
                    text=row["text"],
                    token_count=row["token_count"],
                ),
                float(row["score"]),
                str(row["source_url"] or ""),
            )
            for row in rows
        ]

    async def ping(self) -> bool:
        try:
            async with self._pool.connection() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception:  # noqa: BLE001
            return False

    async def save(
        self,
        *,
        question: str,
        answer: str,
        citations: list[Citation],
        retrieved_chunk_ids: list[str],
        user_id: str | None = None,
        latency_ms: float | None = None,
    ) -> None:
        """Implements `QueryLogPort` — persists `query_logs` (architecture §7)."""
        retrieved_chunks = {
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "citations": [
                {
                    "chunk_id": cite.chunk_id,
                    "accession_no": str(cite.accession_no),
                    "section": cite.section,
                    "source_url": cite.source_url,
                }
                for cite in citations
            ],
        }
        async with self._pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO query_logs (
                    query_id, user_id, question, retrieved_chunks, answer, latency_ms
                ) VALUES (%s, %s, %s, %s::jsonb, %s, %s)
                """,
                (
                    str(uuid4()),
                    user_id or "unknown",
                    question,
                    json.dumps(retrieved_chunks),
                    answer,
                    float(latency_ms or 0.0),
                ),
            )
            await conn.commit()


class PostgresFilingRepository:
    """Companies/filings/cursor view over `PostgresKnowledgeStore`.

    Matches the architecture §2 adapter name (`PostgresFilingRepository`)
    without duplicating the pooled connection; wraps the same store so
    ingestion keeps a single pool while callers that want the
    architecture-named type can depend on this narrower surface.
    """

    def __init__(self, store: PostgresKnowledgeStore) -> None:
        self._store = store

    async def upsert_company(self, cik: CIK, name: str, ticker: str | None = None) -> None:
        await self._store.upsert_company(cik, name, ticker)

    async def save_filing(self, filing: Filing, source_url: str) -> None:
        await self._store.save_filing(filing, source_url)

    async def get_filing(self, accession_no: AccessionNumber) -> Filing | None:
        return await self._store.get_filing(accession_no)

    async def get_last_ingested(self, cik: CIK) -> AccessionNumber | None:
        return await self._store.get_last_ingested(cik)

    async def set_last_ingested(self, cik: CIK, accession_no: AccessionNumber) -> None:
        await self._store.set_last_ingested(cik, accession_no)


class PgVectorStore:
    """pgvector embeddings view over `PostgresKnowledgeStore`.

    Matches the architecture §2 adapter name (`PgVectorStore`); see
    `PostgresFilingRepository` for why this wraps rather than replaces the
    combined store.
    """

    def __init__(self, store: PostgresKnowledgeStore) -> None:
        self._store = store

    async def upsert_embeddings(
        self, items: list[tuple[Chunk, list[float], dict[str, object]]]
    ) -> None:
        await self._store.upsert_embeddings(items)

    async def get_embedding(self, chunk_id: str) -> list[float] | None:
        return await self._store.get_embedding(chunk_id)

    async def search_dense(
        self, query_vector: list[float], *, top_k: int = 5
    ) -> list[tuple[Chunk, float, str]]:
        return await self._store.search_dense(query_vector, top_k=top_k)
