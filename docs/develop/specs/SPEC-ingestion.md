# Spec: ingestion

Module id: `ingestion`  
Depends on: `platform-foundation`  
Umbrella: [SPEC-develop.md](SPEC-develop.md) · Map: [CAPABILITY-MAP.md](CAPABILITY-MAP.md)  
Architecture: [docs/architecture-design.md](../../architecture-design.md) §4  
Operator guide: [docs/edgar-download-guide.md](../../edgar-download-guide.md) · Service README: [services/ingestion/README.md](../../../services/ingestion/README.md)

---

## Objective

Ingest SEC EDGAR filings for a chosen CIK (+ form types) into either the **local** data plane (filesystem + SQLite) or the **Compose** data plane (MinIO + Postgres/pgvector + OpenSearch), with section-aware chunking and OpenAI embeddings—so `query` can retrieve grounded context.

**User:** platform operator via **CLI**, **BFF HTTP API**, or Annex **`/ingest`** UI.

**Success:** Given a fixture CIK + mocked filing HTML, `IngestFiling` produces: raw object key, `filings` row, ≥1 `chunks` row with section metadata, and embedding vectors—verified with fakes. Live SEC + OpenAI runs require `SEC_USER_AGENT` and `OPENAI_API_KEY` (not in default `make test`).

---

## Tech Stack

| Piece | Choice |
|---|---|
| Package | `kb-ingestion` (uv workspace member under `services/ingestion`) |
| Operator surfaces | CLI `kb-ingest`; BFF `POST /v1/ingest` + `GET /v1/filings/{accession}/raw`; Dagster graph stub |
| HTTP | httpx + SEC rate limit (≤10 req/s) + required `User-Agent` |
| Parse | `DocumentParserPort` + **SimpleHtmlSectionParser** (Item 1/1A/1B/2/3/7/7A/8 + 10-Q Part headings); Docling deferred |
| Chunk | Paragraph-first then sentence pack; target **512** / max **768** / overlap **64** tokens |
| Embed | `EmbedderPort` + **`OpenAIEmbedder`** (`text-embedding-3-small`, 1536-d) for live; **`HashEmbedder`** for tests |
| Persist (local) | `LocalFilesystemObjectStore` + `SqliteKnowledgeStore` under `INGEST_DATA_DIR` |
| Persist (compose) | `MinioObjectStore` + `PostgresKnowledgeStore` (pgvector 1536, schema applied on connect) when `KB_DATA_PLANE=compose`; required |
| OpenSearch | `OpenSearchChunkIndex` (`SearchIndexPort`) for BM25 when compose; **optional** — unreachable/unset just skips BM25 indexing |

---

## Commands

```bash
uv sync --group dev
export SEC_USER_AGENT="Annex Knowledge Base you@example.com"
export OPENAI_API_KEY="sk-..."

uv run kb-ingest --cik 320193 --forms 10-K,10-Q,8-K
# or: make ingest CIK=320193 FORMS=10-K

uv run pytest services/ingestion apps/bff/tests/test_ingest.py -q
uv run ruff check services/ingestion
uv run mypy
```

---

## Project Structure

```
services/ingestion/
  pyproject.toml          # script: kb-ingest
  src/kb_ingestion/
    cli.py / __main__.py
    application/
      ports/              # EdgarPort, repos, EmbedderPort, …
      use_cases/          # ingest_filing.py
    domain/
      chunking.py         # paragraph-aware sizing (pure)
    infrastructure/
      edgar/              # HttpEdgarClient
      parsing/            # simple_html_section_parser.py
      embeddings/         # hash_embedder.py, openai_embedder.py
      object_store/       # local_fs.py
      persistence/        # in_memory.py, sqlite_store.py
      schema/             # 001_ingestion.sql, 001_ingestion_sqlite.sql
      wiring.py           # build_local_ingest / build_memory_ingest
      raw_download.py     # resolve stored raw bytes for download API
    presentation/
      definitions.py      # Dagster placeholder graph
  tests/
    unit/
    application/
```

BFF: `apps/bff/.../ingest_router.py` (`Role.OPERATOR`).

---

## HTTP API (BFF)

| Method | Path | Body / notes |
|---|---|---|
| `POST` | `/v1/ingest` | `{ "cik", "form_types": ["10-K","10-Q","8-K"], "force"?: bool }` → accession, chunk_count, `download_url` |
| `GET` | `/v1/filings/{accession_no}/raw` | Attachment download of stored HTML |

Requires `SEC_USER_AGENT` + `OPENAI_API_KEY` on the BFF for live ingest wiring; download works against local SQLite/FS once a filing exists.

---

## Code Style

Same Clean Architecture rules as umbrella. Example:

```python
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
    ) -> None: ...

    async def execute(self, command: IngestFilingCommand) -> IngestFilingResult: ...
```

Live wiring injects `OpenAIEmbedder`; tests inject `HashEmbedder`.

---

## Testing Strategy

| Level | Focus |
|---|---|
| Unit | Chunking bounds; parser sections; OpenAI embedder with httpx mock; CLI env guards |
| Application | `IngestFiling` with fakes / local FS+SQLite |
| BFF | Fake Edgar + HashEmbedder: ingest JSON + raw download |
| Integration (optional) | Live EDGAR + OpenAI — never in default `make test` |

**Never** hit SEC or OpenAI from default `make test`.

---

## Boundaries

**Always**

- SEC `User-Agent` required on real client; throttle ≤10 req/s.
- Persist accession + section on every chunk for citations.
- Incremental: skip accession ≤ `last_ingested_accession` for CIK unless `force`.
- Live paths require `OPENAI_API_KEY` (no silent hash fallback).

**Ask first**

- Adding Docling as a hard dependency in default sync.
- Changing embedding dimensions/model once `query` depends on stored vectors.
- Switching default persist from SQLite to Postgres.

**Never**

- Commit API keys.
- Call live EDGAR/OpenAI in unmarked unit tests.
- Index “all of EDGAR” in this MVP.

---

## Data Model (this module owns)

```sql
companies(cik PK, name, ticker, sic, last_ingested_accession)
filings(accession_no PK, cik FK, form_type, filed_date, period, s3_raw_path, source_url)
chunks(chunk_id PK, accession_no FK, section, text, token_count, chunk_index)
embeddings(chunk_id PK FK, embedding /* JSON array locally; vector(N) on Postgres */, metadata)
```

`financial_facts` table exists (compose) but stays empty — XBRL loading into it is out of MVP scope.

---

## Success Criteria

1. `IngestFiling` application test: fixture HTML → raw stored, filing saved, chunks with sections, embeddings written, cursor updated.
2. `HttpEdgarClient` unit-tested with httpx mock: sends User-Agent; rate limiter within 10/s budget.
3. `SimpleHtmlSectionParser` extracts named sections from fixture HTML; paragraph breaks preserved for chunking.
4. SQLite (+ SQL) schema exists for companies/filings/chunks/embeddings.
5. CLI `kb-ingest` and BFF ingest/download routes covered by tests (fakes).
6. Default `make test` stays green without Docker/network/OpenAI.

---

## Open Questions

None blocking. Example CIK: Apple `320193` / `0000320193`.
