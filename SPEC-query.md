# Spec: query

Module id: `query`  
Depends on: `platform-foundation`, `ingestion`  
Umbrella: [SPEC-develop.md](SPEC-develop.md) · Map: [CAPABILITY-MAP.md](CAPABILITY-MAP.md)  
Architecture: [docs/architecture-design.md](docs/architecture-design.md) §5

---

## Objective

Answer analyst questions with **grounded, cited** responses over ingested chunks: rewrite → hybrid retrieve → rerank → generate → citation validate → stream to the client.

**User:** analyst via BFF (dev auth bypass).

**MVP success:** Given an in-memory corpus of chunks + embeddings from a fixture filing, `AnswerQuery` returns an answer that cites real chunk ids; `CitationValidator` rejects deliberately ungrounded drafts; BFF exposes `POST /v1/query` with **SSE** streaming; default tests use fakes (no OpenAI/OpenSearch/Docker).

---

## Tech Stack

| Piece | Choice |
|---|---|
| Package | `kb-query` under `services/query` |
| Orchestration | LangGraph `StateGraph` (rewrite → retrieve → generate → validate) |
| Hybrid retrieval | In-memory dense cosine + keyword overlap → **RRF**; OpenSearch adapter deferred |
| Rerank | Identity/pass-through port (cross-encoder later) |
| LLM | `LLMPort` + `FakeLLM` for tests; OpenAI adapter deferred behind port |
| Embed query | `EmbedderPort` + **`OpenAIQueryEmbedder`** (`text-embedding-3-small`) for live; **`HashQueryEmbedder`** for tests (must match ingest dimensions) |
| API | FastAPI SSE on BFF `POST /v1/query` |

---

## Commands

```bash
uv sync --group dev
uv run pytest services/query apps/bff -q
make test lint typecheck
uv run uvicorn kb_bff.main:app --reload --port 8000
# POST /v1/query with JSON {"question":"..."} — Accept text/event-stream
```

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
      retrieval/in_memory_hybrid.py
      rerank/noop_reranker.py
    presentation/graph.py          # LangGraph wiring
  tests/unit/ tests/application/
apps/bff/ ... presentation/query_router.py
```

---

## Testing Strategy

- Unit: `CitationValidator`, RRF fusion ordering, FakeLLM citation formatting
- Application: `AnswerQuery` end-to-end with seeded corpus
- BFF: TestClient SSE / JSON event stream contains `token` / `done` / `sources`

**Never** call live LLM in unmarked tests.

---

## Boundaries

**Always:** Persist/return citation trail (chunk_id, accession, section, source_url). Reject ungrounded answers via validator.

**Ask first:** Making OpenAI/OpenSearch required deps; changing SSE event schema once UI depends on it.

**Never:** Return answers without attempted citation validation; hit SEC from query path.

---

## Success Criteria

1. Seeded corpus → answer includes ≥1 citation matching a retrieved chunk.
2. Validator unit test rejects draft that claims facts with unknown chunk ids.
3. Hybrid retriever returns relevant chunk for a question overlapping fixture text.
4. LangGraph graph compiles and runs the four stages.
5. `POST /v1/query` streams SSE events; `auth_mode` remains `dev_bypass`.
6. `make test lint typecheck` green offline.

---

## Open Questions

None blocking. OpenAI wiring waits for env secrets + ask-first.
