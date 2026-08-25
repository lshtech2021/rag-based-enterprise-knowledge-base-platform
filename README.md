# RAG Enterprise Knowledge Base Platform

See [SPEC-develop.md](SPEC-develop.md) and [CAPABILITY-MAP.md](CAPABILITY-MAP.md).

EDGAR download how-to: [docs/edgar-download-guide.md](docs/edgar-download-guide.md).

## Quick start

```bash
docker compose -f infra/docker-compose.yml up -d  # requires Docker
uv sync --group dev
make test lint typecheck
uv run uvicorn kb_bff.main:app --reload --port 8000
curl -s localhost:8000/healthz

# Web UI (Annex)
cd apps/web && npm install && npm run dev
```

Open http://localhost:3000 — console and reports call the BFF (`NEXT_PUBLIC_BFF_URL`).
