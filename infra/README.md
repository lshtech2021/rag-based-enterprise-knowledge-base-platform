# Local data plane

```bash
# Core services (Postgres+pgvector, Redis, MinIO)
docker compose -f infra/docker-compose.yml up -d

# Compose RAG path also needs OpenSearch (BM25)
docker compose -f infra/docker-compose.yml --profile opensearch up -d

docker compose -f infra/docker-compose.yml ps
```

| Service | Port | Notes |
|---|---|---|
| Postgres + pgvector | 5432 | user/pass/db: `kb` / `kb` / `knowledge_base`; schema via `initdb/` |
| Redis | 6379 | cache + Redis Streams |
| MinIO | 9000 (API), 9001 (console) | `minioadmin` / `minioadmin`; bucket `kb-filings` |
| OpenSearch | 9200 | required for `KB_DATA_PLANE=compose`: `--profile opensearch` |

## App switch

```bash
# Default offline path (SQLite + local FS)
export KB_DATA_PLANE=local

# Compose-backed path
export KB_DATA_PLANE=compose
export DATABASE_URL=postgresql://kb:kb@localhost:5432/knowledge_base
export MINIO_ENDPOINT=localhost:9000
export MINIO_ACCESS_KEY=minioadmin
export MINIO_SECRET_KEY=minioadmin
export OPENSEARCH_URL=http://localhost:9200
export OPENAI_API_KEY=sk-...
export SEC_USER_AGENT="Annex Knowledge Base you@example.com"
```

Default app auth for local BFF: `AUTH_MODE=dev_bypass` (see repo `.env.example`).

Integration tests (optional):

```bash
KB_RUN_COMPOSE_TESTS=1 uv run pytest -m integration -q
```
