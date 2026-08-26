# Query service

Hybrid RAG Q&A with citations. Spec: [`SPEC-query.md`](../../SPEC-query.md)

## Local demo (shared with ingest)

Uses the same `INGEST_DATA_DIR` SQLite corpus written by `kb-ingest` / `POST /v1/ingest`.

```bash
export OPENAI_API_KEY=sk-...
export INGEST_DATA_DIR=data/ingestion
# Optional OpenAI-compatible gateway:
# export OPENAI_BASE_URL=https://your-proxy.example/v1
# export OPENAI_CHAT_MODEL=gpt-4o-mini
# export OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# After ingesting at least one filing:
uv run uvicorn kb_bff.main:app --reload --port 8000
# POST /v1/query  {"question":"..."}  Accept: text/event-stream
# GET  /healthz   → query_configured, corpus_chunks
```

Wiring: `build_local_answer_query` (SQLite) or `build_compose_answer_query` (pgvector + OpenSearch) depending on `KB_DATA_PLANE`.

## Tests

```bash
uv run pytest services/query apps/bff -q
# Optional Compose smoke:
KB_RUN_COMPOSE_TESTS=1 uv run pytest -m integration -q
```
