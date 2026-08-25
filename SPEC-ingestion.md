# Spec: ingestion

Module id: `ingestion`  
Depends on: `platform-foundation`  
Umbrella: [SPEC-develop.md](SPEC-develop.md) · Map: [CAPABILITY-MAP.md](CAPABILITY-MAP.md)  
Architecture: [docs/architecture-design.md](docs/architecture-design.md) §4

---

## Objective

Ingest SEC EDGAR filings for a curated CIK set into MinIO (raw) + Postgres (metadata/chunks) + pgvector (embeddings), with section-aware chunking and incremental dedup—so `query` can retrieve grounded context.

**User:** platform operator running Dagster (or a CLI) for one company/filing.

**MVP success:** Given a fixture CIK + mocked/fixture filing HTML, `IngestFiling` produces: raw object key, `filings` row, ≥1 `chunks` row with section metadata, and embedding vectors—fully verified with fakes in unit/application tests. Real HTTP/EDGAR and Compose integrations are optional (`@pytest.mark.integration`).

---

## Tech Stack

| Piece | Choice |
|---|---|
| Package | `kb-ingestion` (uv workspace member under `services/ingestion`) |
| Orchestration | Dagster asset graph (definitions importable; `dagster dev` later) |
| HTTP | httpx + SEC rate limit (≤10 req/s) + required `User-Agent` |
| Parse (MVP) | `DocumentParserPort` + **SimpleHtmlSectionParser** (Item 1A / MD&A heuristics); Docling adapter deferred behind same port |
| Embed (MVP) | `EmbedderPort` + deterministic `HashEmbedder` for tests; OpenAI adapter optional via env |
| Persist | SQL schema + repository ports; **InMemory** adapters for unit tests; Postgres/pgvector + MinIO adapters when Compose is up |
| OpenSearch | Port stub only (index no-op); real BM25 indexing deferred |

---

## Commands

```bash
uv sync --group dev
uv run pytest services/ingestion packages -q
uv run ruff check services/ingestion
uv run mypy
# Optional when Docker available:
docker compose -f infra/docker-compose.yml up -d
uv run dagster dev -f services/ingestion/src/kb_ingestion/presentation/definitions.py
```

---

## Project Structure

```
services/ingestion/
  pyproject.toml
  src/kb_ingestion/
    application/
      ports/          # EdgarPort, FilingRepository, ChunkRepository, VectorStorePort,
                      # EmbedderPort, DocumentParserPort, IngestionCursorPort
      use_cases/      # ingest_filing.py
    domain/
      chunking.py     # section-aware chunk sizing rules (pure)
    infrastructure/
      edgar/          # HttpEdgarClient (+ rate limiter)
      parsing/        # simple_html_section_parser.py
      embeddings/     # hash_embedder.py, openai_embedder.py (optional)
      persistence/    # in_memory_*.py; postgres_*.py (thin, may stub if no Docker)
      object_store/   # in_memory_object_store.py
      schema/         # 001_ingestion.sql
    presentation/
      definitions.py  # Dagster assets: raw_filing → parsed → chunks → embeddings
  tests/
    unit/
    application/
```

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

---

## Testing Strategy

| Level | Focus |
|---|---|
| Unit | `normalize`/chunking bounds; parser splits sections from fixture HTML |
| Application | `IngestFiling` with all fakes — asserts filing + chunks + vectors + cursor advance |
| Integration (optional) | Live EDGAR fetch with recorded User-Agent; Postgres/MinIO |

**Never** hit SEC or OpenAI from default `make test`.

---

## Boundaries

**Always**

- SEC `User-Agent` required on real client; throttle ≤10 req/s.
- Persist accession + section on every chunk for citations.
- Incremental: skip accession ≤ `last_ingested_accession` for CIK when cursor set.

**Ask first**

- Adding Docling/OpenAI as hard dependencies in default sync.
- Changing schema once `query` depends on it.

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
embeddings(chunk_id PK FK, embedding vector(N), metadata JSONB)
```

`financial_facts` / OpenSearch documents: out of MVP scope (ports may no-op).

---

## Success Criteria

1. `IngestFiling` application test: fixture HTML → raw stored, filing saved, chunks with sections, embeddings written, cursor updated.
2. `HttpEdgarClient` unit-tested with httpx mock: sends User-Agent; rate limiter allows burst within 10/s budget.
3. `SimpleHtmlSectionParser` extracts at least one named section from fixture 10-K-like HTML.
4. SQL schema file exists for companies/filings/chunks/embeddings.
5. Dagster definitions expose asset graph `raw_filing → parsed_doc → chunks → embeddings` wiring the use case (executable with fakes/resources).
6. Default `make test` stays green without Docker/network.

---

## Open Questions

None blocking. Curated CIK list for live runs: start with Apple `0000320193` as the documented example only.
