# Ingestion service

EDGAR ETL: fetch → store → parse → chunk → embed.

Spec: [`SPEC-ingestion.md`](../../SPEC-ingestion.md)  
Download guide: [`docs/edgar-download-guide.md`](../../docs/edgar-download-guide.md)

## Ingest a filing (local)

Uses live SEC HTTP + **filesystem raw store** + **SQLite** + **OpenAI embeddings** (`text-embedding-3-small`).

```bash
uv sync --group dev

export SEC_USER_AGENT="Annex Knowledge Base you@example.com"
export OPENAI_API_KEY="sk-..."

# Latest 10-K/10-Q/8-K for Apple (CIK 320193)
uv run kb-ingest --cik 320193

# Restrict form types
uv run kb-ingest --cik 320193 --forms 10-K,10-Q

# Or via Make
make ingest CIK=320193 FORMS=10-K
```

Outputs land under `data/ingestion/` by default:

- `raw/filings/...` — downloaded HTML
- `ingestion.sqlite3` — companies, filings, chunks, embeddings, cursor

Re-run is incremental (skips if accession ≤ cursor). Force with `--force`.

## HTTP API + UI

With BFF running (`OPENAI_API_KEY` + `SEC_USER_AGENT` set):

- `POST /v1/ingest` — `{ "cik", "form_types": ["10-K"], "force": false }`
- `GET /v1/filings/{accession_no}/raw` — download stored HTML
- Web: `/ingest` page (Ingest nav link)

## Tests / Dagster

```bash
uv run pytest services/ingestion apps/bff/tests/test_ingest.py -q
# uv run dagster dev -f services/ingestion/src/kb_ingestion/presentation/definitions.py
```

Layers: `application` / `domain` / `infrastructure` / `presentation`.
