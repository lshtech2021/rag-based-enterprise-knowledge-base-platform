# RAG Enterprise Knowledge Base Platform

See [SPEC-develop.md](SPEC-develop.md) and [CAPABILITY-MAP.md](CAPABILITY-MAP.md).

EDGAR download how-to: [docs/edgar-download-guide.md](docs/edgar-download-guide.md).  
Ingestion service: [services/ingestion/README.md](services/ingestion/README.md).

## Quick start

```bash
# Optional data plane (Postgres/MinIO/Redis) — not required for local ingest
docker compose -f infra/docker-compose.yml up -d

uv sync --group dev
cp .env.example .env   # set SEC_USER_AGENT + OPENAI_API_KEY for live ingest
make test lint typecheck

# BFF
uv run uvicorn kb_bff.main:app --reload --port 8000
curl -s localhost:8000/healthz

# Web UI (Annex)
cd apps/web && npm install && npm run dev
```

Open http://localhost:3000 — **Console**, **Ingest**, and **Reports** call the BFF (`NEXT_PUBLIC_BFF_URL`).

### Ingest a filing (no Docker)

```bash
export SEC_USER_AGENT="Annex Knowledge Base you@example.com"
export OPENAI_API_KEY="sk-..."
make ingest CIK=320193 FORMS=10-K
# data under data/ingestion/
```
