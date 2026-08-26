# Ingestion service

EDGAR ETL: fetch → store → parse → chunk → embed.

Spec: [`SPEC-ingestion.md`](../../docs/develop/specs/SPEC-ingestion.md)  
Download guide: [`docs/edgar-download-guide.md`](../../docs/edgar-download-guide.md)

## Ingest a filing (local)

Uses live SEC HTTP + **filesystem raw store** + **SQLite** + embeddings
(`EMBEDDING_PROVIDER=openai` → `text-embedding-3-small`, or
`dashscope`/`qwen` → Alibaba `qwen3.7-text-embedding`). Vectors stay at
`EMBEDDING_DIMENSIONS` (default 1536) to match `vector(1536)`.

```bash
uv sync --group dev

export SEC_USER_AGENT="Annex Knowledge Base you@example.com"
export EMBEDDING_PROVIDER=openai   # or dashscope / qwen
export OPENAI_API_KEY="sk-..."
# Optional OpenAI-compatible gateway:
# export OPENAI_BASE_URL=https://your-proxy.example/v1
# export OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Alibaba DashScope / Qwen (OpenAI-compatible mode; separate client from chat):
# export EMBEDDING_PROVIDER=dashscope
# export DASHSCOPE_API_KEY="sk-..."
# export DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
# export DASHSCOPE_EMBEDDING_MODEL=qwen3.7-text-embedding

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

## Ingest a filing (Compose)

```bash
# Postgres + MinIO are required for compose; OpenSearch is optional (BM25)
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml --profile opensearch up -d  # optional

export KB_DATA_PLANE=compose
export DATABASE_URL=postgresql://kb:kb@localhost:5432/knowledge_base
export MINIO_ENDPOINT=localhost:9000
export MINIO_ACCESS_KEY=minioadmin
export MINIO_SECRET_KEY=minioadmin
export OPENSEARCH_URL=http://localhost:9200
export OPENSEARCH_USERNAME=admin
export OPENSEARCH_PASSWORD=admin
export SEC_USER_AGENT="Annex Knowledge Base you@example.com"
export EMBEDDING_PROVIDER=openai   # or dashscope / qwen
export OPENAI_API_KEY="sk-..."
# export DASHSCOPE_API_KEY="sk-..."  # when EMBEDDING_PROVIDER=dashscope

uv run kb-ingest --cik 320193 --backend compose
```

Stores raw HTML in MinIO, metadata/vectors in Postgres/pgvector (schema
applied automatically on connect), and — if OpenSearch is reachable — BM25
docs in OpenSearch (basic auth from `OPENSEARCH_USERNAME` /
`OPENSEARCH_PASSWORD` when username is set). Without OpenSearch, ingestion still
succeeds; query just falls back to dense-only pgvector search.

## HTTP API + UI

With BFF running (`SEC_USER_AGENT` + embedding key set — `OPENAI_API_KEY` or
`DASHSCOPE_API_KEY` depending on `EMBEDDING_PROVIDER`):

- `POST /v1/ingest` — `{ "cik", "form_types": ["10-K"], "force": false }`
- `GET /v1/filings/{accession_no}/raw` — download stored HTML
- Web: `/ingest` page (Ingest nav link)

## Tests / Dagster

```bash
uv run pytest services/ingestion apps/bff/tests/test_ingest.py -q
# uv run dagster dev -f services/ingestion/src/kb_ingestion/presentation/definitions.py
```

Layers: `application` / `domain` / `infrastructure` / `presentation`.
