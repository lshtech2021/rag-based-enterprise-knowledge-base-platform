"""Postgres-backed report persistence (architecture §7 `reports` / `report_citations`).

`reports.params` (JSONB) carries the fields the minimal architecture schema
doesn't break out into columns (company, period, title, per-section
title/question/body) so `report_citations` can stay exactly the
citation-provenance table the architecture describes, without inventing an
extra `report_sections` table.

Markdown is kept in the `markdown` column (fast reads for `GET
/v1/reports/{id}`) *and* optionally uploaded to an object store (MinIO in
Compose) with the returned URI recorded in `s3_output_path`, matching the
architecture's "stored in S3, downloadable" intent for report artifacts.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Protocol, cast, runtime_checkable

from kb_domain import AccessionNumber, Citation
from kb_report.application.ports import ReportSectionResult, StoredReport
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS reports (
        report_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        template TEXT NOT NULL,
        params JSONB NOT NULL DEFAULT '{}'::jsonb,
        markdown TEXT NOT NULL,
        s3_output_path TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS report_citations (
        report_id TEXT NOT NULL REFERENCES reports (report_id),
        section_id TEXT NOT NULL,
        chunk_id TEXT NOT NULL,
        accession_no TEXT NOT NULL,
        section TEXT NOT NULL,
        source_url TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS report_citations_report_idx ON report_citations (report_id)",
)


@runtime_checkable
class ReportObjectStore(Protocol):
    async def put_bytes(self, key: str, body: bytes, content_type: str) -> str: ...


async def _ensure_schema(database_url: str) -> None:
    conn = await AsyncConnection.connect(database_url)
    try:
        for statement in _SCHEMA_STATEMENTS:
            await conn.execute(statement)
        await conn.commit()
    finally:
        await conn.close()


class PostgresReportRepository:
    """`ReportRepository` against Postgres, with an optional object-store artifact."""

    def __init__(
        self,
        pool: AsyncConnectionPool[Any],
        *,
        object_store: ReportObjectStore | None = None,
        artifact_prefix: str = "reports",
    ) -> None:
        self._pool = pool
        self._object_store = object_store
        self._artifact_prefix = artifact_prefix

    @classmethod
    async def connect(
        cls,
        database_url: str,
        *,
        object_store: ReportObjectStore | None = None,
        artifact_prefix: str = "reports",
        min_size: int = 1,
        max_size: int = 4,
        ensure_schema: bool = True,
    ) -> PostgresReportRepository:
        if ensure_schema:
            await _ensure_schema(database_url)
        pool: AsyncConnectionPool[Any] = AsyncConnectionPool(
            conninfo=database_url,
            min_size=min_size,
            max_size=max_size,
            kwargs={"row_factory": dict_row},
            open=False,
        )
        await pool.open()
        return cls(pool, object_store=object_store, artifact_prefix=artifact_prefix)

    async def aclose(self) -> None:
        await self._pool.close()

    async def save(self, report: StoredReport) -> None:
        s3_output_path: str | None = None
        if self._object_store is not None:
            key = f"{self._artifact_prefix}/{report.report_id}.md"
            s3_output_path = await self._object_store.put_bytes(
                key, report.markdown.encode("utf-8"), "text/markdown"
            )

        params = {
            "company": report.company,
            "period": report.period,
            "title": report.title,
            "sections": [
                {
                    "section_id": section.section_id,
                    "title": section.title,
                    "question": section.question,
                    "body": section.body,
                }
                for section in report.sections
            ],
        }

        async with self._pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO reports (
                    report_id, user_id, template, params, markdown, s3_output_path, created_at
                ) VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s)
                ON CONFLICT (report_id) DO UPDATE SET
                    params = EXCLUDED.params,
                    markdown = EXCLUDED.markdown,
                    s3_output_path = EXCLUDED.s3_output_path
                """,
                (
                    report.report_id,
                    report.user_id,
                    report.template_id,
                    json.dumps(params),
                    report.markdown,
                    s3_output_path,
                    report.created_at,
                ),
            )
            await conn.execute(
                "DELETE FROM report_citations WHERE report_id = %s", (report.report_id,)
            )
            for section in report.sections:
                for cite in section.citations:
                    await conn.execute(
                        """
                        INSERT INTO report_citations (
                            report_id, section_id, chunk_id, accession_no, section, source_url
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            report.report_id,
                            section.section_id,
                            cite.chunk_id,
                            str(cite.accession_no),
                            cite.section,
                            cite.source_url,
                        ),
                    )
            await conn.commit()

    async def get(self, report_id: str) -> StoredReport | None:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT * FROM reports WHERE report_id = %s", (report_id,)
            )
            row = cast(dict[str, Any] | None, await cur.fetchone())
            if row is None:
                return None
            cite_cur = await conn.execute(
                """
                SELECT section_id, chunk_id, accession_no, section, source_url
                FROM report_citations
                WHERE report_id = %s
                ORDER BY section_id
                """,
                (report_id,),
            )
            citation_rows = cast(list[dict[str, Any]], await cite_cur.fetchall())

        params = row["params"] or {}
        if isinstance(params, str):
            params = json.loads(params)

        citations_by_section: dict[str, list[Citation]] = {}
        for crow in citation_rows:
            citations_by_section.setdefault(crow["section_id"], []).append(
                Citation(
                    chunk_id=crow["chunk_id"],
                    accession_no=AccessionNumber(crow["accession_no"]),
                    section=crow["section"],
                    source_url=crow["source_url"],
                )
            )

        sections = tuple(
            ReportSectionResult(
                section_id=meta["section_id"],
                title=meta["title"],
                question=meta["question"],
                body=meta["body"],
                citations=tuple(citations_by_section.get(meta["section_id"], ())),
            )
            for meta in params.get("sections", [])
        )

        created_at = row["created_at"]
        if not isinstance(created_at, datetime):
            created_at = datetime.now(UTC)

        return StoredReport(
            report_id=row["report_id"],
            user_id=row["user_id"],
            template_id=row["template"],
            title=str(params.get("title") or row["template"]),
            company=str(params.get("company") or ""),
            period=str(params.get("period") or ""),
            markdown=row["markdown"],
            sections=sections,
            created_at=created_at,
        )

    async def ping(self) -> bool:
        try:
            async with self._pool.connection() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception:  # noqa: BLE001
            return False
