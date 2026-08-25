"""Ingest a single filing for a CIK through the RAG data plane."""

from __future__ import annotations

from dataclasses import dataclass

from kb_application_ports import ObjectStorePort
from kb_domain import CIK, AccessionNumber, Chunk, Filing
from kb_ingestion.application.ports import (
    ChunkRepository,
    DocumentParserPort,
    EdgarPort,
    EmbedderPort,
    FilingRepository,
    IngestionCursorPort,
    VectorStorePort,
)
from kb_ingestion.domain.chunking import iter_chunk_payloads


@dataclass(frozen=True, slots=True)
class IngestFilingCommand:
    cik: CIK
    form_types: tuple[str, ...] = ("10-K", "10-Q", "8-K")
    force: bool = False


@dataclass(frozen=True, slots=True)
class IngestFilingResult:
    accession_no: AccessionNumber
    skipped: bool
    chunk_count: int
    s3_raw_path: str | None


class IngestFiling:
    def __init__(
        self,
        edgar: EdgarPort,
        store: ObjectStorePort,
        filings: FilingRepository,
        parser: DocumentParserPort,
        embedder: EmbedderPort,
        chunks: ChunkRepository,
        vectors: VectorStorePort,
        cursor: IngestionCursorPort,
    ) -> None:
        self._edgar = edgar
        self._store = store
        self._filings = filings
        self._parser = parser
        self._embedder = embedder
        self._chunks = chunks
        self._vectors = vectors
        self._cursor = cursor

    async def execute(self, command: IngestFilingCommand) -> IngestFilingResult:
        meta = await self._edgar.fetch_latest_filing(command.cik, command.form_types)
        last = await self._cursor.get_last_ingested(command.cik)
        if not command.force and last is not None and str(meta.accession_no) <= str(last):
            return IngestFilingResult(
                accession_no=meta.accession_no,
                skipped=True,
                chunk_count=0,
                s3_raw_path=None,
            )

        raw = await self._edgar.download_filing_document(meta)
        key = f"filings/{meta.cik}/{meta.accession_no}/{meta.primary_document}"
        s3_path = await self._store.put_bytes(key, raw, content_type="text/html")

        await self._filings.upsert_company(meta.cik, meta.company_name)
        filing = Filing(
            accession_no=meta.accession_no,
            cik=meta.cik,
            form_type=meta.form_type,
            filed_date=meta.filed_date,
            s3_raw_path=s3_path,
        )
        await self._filings.save_filing(filing, source_url=meta.source_url)

        sections = self._parser.parse(raw)
        built: list[Chunk] = []
        for index, (section, text, token_count) in enumerate(
            iter_chunk_payloads([(s.name, s.text) for s in sections])
        ):
            chunk_id = f"{meta.accession_no}:{index}"
            built.append(
                Chunk(
                    chunk_id=chunk_id,
                    accession_no=meta.accession_no,
                    section=section,
                    text=text,
                    token_count=token_count,
                )
            )
        await self._chunks.replace_chunks(meta.accession_no, built)

        vectors = await self._embedder.embed_documents([c.text for c in built])
        await self._vectors.upsert_embeddings(
            [
                (
                    chunk,
                    vector,
                    {
                        "accession_no": str(chunk.accession_no),
                        "section": chunk.section,
                        "source_url": meta.source_url,
                    },
                )
                for chunk, vector in zip(built, vectors, strict=True)
            ]
        )
        await self._cursor.set_last_ingested(meta.cik, meta.accession_no)
        return IngestFilingResult(
            accession_no=meta.accession_no,
            skipped=False,
            chunk_count=len(built),
            s3_raw_path=s3_path,
        )
