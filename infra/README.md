# Local data plane

```bash
# Core services (Postgres+pgvector, Redis, MinIO) — required for KB_DATA_PLANE=compose
docker compose -f infra/docker-compose.yml up -d

# BM25 (optional — hybrid retrieval degrades to dense-only pgvector without it)
docker compose -f infra/docker-compose.yml --profile opensearch up -d

docker compose -f infra/docker-compose.yml ps
```

| Service | Port | Notes |
|---|---|---|
| Postgres + pgvector | 5432 | user/pass/db: `kb` / `kb` / `knowledge_base`; full app schema (`initdb/`, also applied on connect) |
| Redis | 6379 | cache + Redis Streams (not yet wired into ingest/query) |
| MinIO | 9000 (API), 9001 (console) | `minioadmin` / `minioadmin`; bucket `kb-filings` — raw filings + report Markdown artifacts |
| OpenSearch | 9200 | optional for `KB_DATA_PLANE=compose`: `--profile opensearch`; BM25 half of hybrid retrieval |

Postgres and MinIO are **required** once you select `compose`; ingest/query/BFF
fail to start if either is unreachable. OpenSearch is optional — ingest skips
BM25 indexing and query falls back to dense-only pgvector search if it's
unset or unreachable.

The full schema (`companies`, `filings`, `chunks`, `embeddings`,
`financial_facts`, `reports`, `report_citations`, `query_logs`) is applied
idempotently by the app on every connect (`PostgresKnowledgeStore.connect` /
`PostgresReportRepository.connect`), not only by `initdb/` on a fresh volume —
so this also works against a Postgres you provisioned yourself, as long as a
superuser has already run `CREATE EXTENSION vector` once.

## App switch

```bash
# Default offline path (SQLite + local FS + in-memory reports)
export KB_DATA_PLANE=local

# Compose-backed path (Postgres/pgvector + MinIO always; OpenSearch optional)
export KB_DATA_PLANE=compose
export DATABASE_URL=postgresql://kb:kb@localhost:5432/knowledge_base
export MINIO_ENDPOINT=localhost:9000
export MINIO_ACCESS_KEY=minioadmin
export MINIO_SECRET_KEY=minioadmin
export MINIO_BUCKET=kb-filings
export OPENSEARCH_URL=http://localhost:9200
export OPENSEARCH_USERNAME=admin
export OPENSEARCH_PASSWORD=admin
export OPENAI_API_KEY=sk-...
export SEC_USER_AGENT="Annex Knowledge Base you@example.com"
```

Under `compose`, the BFF also switches report persistence to Postgres +
MinIO (`PostgresReportRepository`) and writes a `query_logs` row per answered
question. `GET /healthz` reports `postgres_ok` / `minio_ok` / `opensearch_ok`
readiness flags when `data_plane` is `compose`. For secured OpenSearch clusters,
set `OPENSEARCH_USERNAME` / `OPENSEARCH_PASSWORD` (leave username empty to skip
basic auth against a local `DISABLE_SECURITY_PLUGIN` compose profile).

Default app auth for local BFF: `AUTH_MODE=dev_bypass` (see repo `.env.example`).
BFF log verbosity: `LOG_LEVEL=INFO` (use `DEBUG` to include `/healthz` access lines).

Integration tests (optional, hit the live services above):

```bash
KB_RUN_COMPOSE_TESTS=1 uv run pytest -m integration -q
```
