# Spec: query

Module id: `query`  
Depends on: `platform-foundation`, `ingestion`  
Umbrella: [SPEC-develop.md](SPEC-develop.md) · Map: [CAPABILITY-MAP.md](CAPABILITY-MAP.md)  
Architecture: [docs/architecture-design.md](../../architecture-design.md) §5

---

## Objective

Answer analyst questions with **grounded, cited** responses over ingested chunks: rewrite → hybrid retrieve → rerank → generate → citation validate → stream to the client.

**User:** analyst via BFF (dev auth bypass).

**MVP success:** Given a corpus of chunks + embeddings (in-memory fakes in tests; SQLite from `INGEST_DATA_DIR` live), `AnswerQuery` returns an answer that cites real chunk ids; `CitationValidator` rejects deliberately ungrounded drafts; BFF exposes `POST /v1/query` with **SSE** streaming; default tests use fakes (no OpenAI/OpenSearch/Docker).

---

## Tech Stack

| Piece | Choice |
|---|---|
| Package | `kb-query` under `services/query` |
| Orchestration | LangGraph `StateGraph` (rewrite → retrieve → generate → validate) |
| Hybrid retrieval | Local: in-memory dense+keyword RRF over SQLite corpus. Compose: **pgvector dense + OpenSearch BM25 → RRF** (`ComposeHybridRetriever`); falls back to `DenseOnlyRetriever` (pgvector only) if OpenSearch is unset/unreachable |
| Query audit | Compose: `query_logs` row per answer via `QueryLogPort` (`AnswerQuery(logs=...)`); local: no-op (`logs=None`) |
| Rerank | Identity/pass-through port (cross-encoder later) |
| LLM | `LLMPort` + `FakeLLM` for tests; **`OpenAIChatLLM`** for live BFF |
| Embed query | `EmbedderPort` + **`OpenAIQueryEmbedder`** (`text-embedding-3-small`) for live; **`HashQueryEmbedder`** for tests (must match ingest dimensions) |
| Local wiring | `build_local_answer_query(data_dir=…)` reads `INGEST_DATA_DIR/ingestion.sqlite3` |
| Compose wiring | `build_compose_answer_query` when `KB_DATA_PLANE=compose` |
| API | FastAPI SSE on BFF `POST /v1/query` |

---

## Commands

```bash
uv sync --group dev
export OPENAI_API_KEY=sk-...
export INGEST_DATA_DIR=data/ingestion   # same dir used by kb-ingest

uv run pytest services/query apps/bff -q
make test lint typecheck
uv run uvicorn kb_bff.main:app --reload --port 8000
# POST /v1/query with JSON {"question":"..."} — Accept text/event-stream
```

Live BFF lifespan wires query + report when `OPENAI_API_KEY` is set; `GET /healthz` reports `query_configured` / `corpus_chunks`.

---

## Project Structure

```
services/query/
  src/kb_query/
    domain/citation_validator.py
    application/ports/
    application/use_cases/answer_query.py
    infrastructure/
      embeddings/hash_query_embedder.py
      embeddings/openai_query_embedder.py
      llm/fake_llm.py
      llm/openai_chat_llm.py
      retrieval/in_memory_hybrid.py
      rerank/noop_reranker.py
      wiring.py                    # build_local_answer_query
    presentation/graph.py          # LangGraph wiring
  tests/unit/ tests/application/
apps/bff/ ... query_router.py
```

---

## Testing Strategy

- Unit: `CitationValidator`, RRF fusion ordering, FakeLLM / OpenAIChatLLM (httpx mock)
- Application: `AnswerQuery` end-to-end with seeded corpus
- BFF: TestClient SSE / JSON event stream contains `token` / `done` / `sources`; healthz flags without keys

**Never** call live LLM in unmarked tests.

---

## Boundaries

**Always:** Persist/return citation trail (chunk_id, accession, section, source_url). Reject ungrounded answers via validator.

**Ask first:** Making OpenSearch required; changing SSE event schema once UI depends on it; swapping embedding dimensions after corpus exists.

**Never:** Return answers without attempted citation validation; hit SEC from query path.

---

## Success Criteria

1. Seeded corpus → answer includes ≥1 citation matching a retrieved chunk.
2. Validator unit test rejects draft that claims facts with unknown chunk ids.
3. Hybrid retriever returns relevant chunk for a question overlapping fixture text.
4. LangGraph graph compiles and runs the four stages.
5. `POST /v1/query` streams SSE events; `auth_mode` remains `dev_bypass`.
6. Local wiring loads SQLite corpus shared with ingest (`list_retrieval_corpus`).
7. `make test lint typecheck` green offline.

---

## Open Questions

None blocking. Cross-encoder reranking remains a later slice.
