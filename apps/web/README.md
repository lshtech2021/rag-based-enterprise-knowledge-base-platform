# Annex web (apps/web)

Next.js App Router UI for the knowledge base BFF.

## Pages

| Route | Purpose |
|---|---|
| `/` | Landing |
| `/console` | Grounded chat (SSE `POST /v1/query`) |
| `/ingest` | EDGAR ingest by CIK + form types; download raw filing |
| `/reports` | Quarterly risk summary report builder |

## Local run

```bash
# Terminal 1 — BFF (from repo root)
export SEC_USER_AGENT="Annex Knowledge Base you@example.com"
export OPENAI_API_KEY="sk-..."   # required for live ingest
uv run uvicorn kb_bff.main:app --reload --port 8000

# Terminal 2 — web
cd apps/web
cp .env.example .env.local   # NEXT_PUBLIC_BFF_URL=http://localhost:8000
npm install && npm run dev
```

Open http://localhost:3000.
