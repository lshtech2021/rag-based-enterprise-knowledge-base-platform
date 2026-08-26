# Spec: observability

Module id: `observability`  
Depends on: `query`, `report`  
Umbrella: [SPEC-develop.md](SPEC-develop.md) · Map: [CAPABILITY-MAP.md](CAPABILITY-MAP.md)

---

## Objective

Make production RAG behavior **visible and regressible**: request/query spans, LLM/retrieval observation hooks, and an offline faithfulness-style eval gate—without requiring live Langfuse/Phoenix in CI.

**Users:** platform operators debugging latency/hallucinations; CI catching citation regressions.

**MVP success:**  
- OpenTelemetry-compatible tracer with in-memory exporter for tests  
- BFF request spans + query/report operation spans  
- `LlmObserverPort` records generation/retrieval events (in-memory; Langfuse adapter stubbed behind port)  
- Offline eval checks that answers retain `[cite:…]` markers against golden fixtures  
- Default `make test` stays green offline  

---

## Tech Stack

| Piece | Choice |
|---|---|
| Package | `kb-observability` in `packages/observability` |
| Tracing | `opentelemetry-api` + `opentelemetry-sdk` (in-memory exporter) |
| LLM eval hooks | `LlmObserverPort` + `InMemoryLlmObserver` (Langfuse later) |
| Offline eval | Heuristic faithfulness/citation gate (Ragas adapter deferred behind port) |

---

## Commands

```bash
uv sync --group dev
uv run pytest packages/observability apps/bff -q
make test lint typecheck
```

---

## Project Structure

```
packages/observability/
  src/kb_observability/
    application/ports.py
    infrastructure/otel_tracer.py
    infrastructure/in_memory_observer.py
    eval/citation_faithfulness.py
  tests/
apps/bff/...  # middleware + wire observer on app.state
```

---

## Boundaries

**Always:** Instrument without leaking secrets/tokens into spans; tests use in-memory backends.

**Ask first:** Adding Langfuse/Phoenix as required runtime deps; shipping OTLP exporter defaults.

**Never:** Fail requests solely because the observer is down (best-effort recording).

---

## Success Criteria

1. Creating a span via configured tracer is visible in the in-memory exporter.
2. BFF middleware creates a span per request (`http.method`, `http.route`).
3. Query path records at least one LLM/retrieval observation event when observer is configured.
4. Offline citation faithfulness eval fails on uncited answers and passes on cited ones.
5. `make test lint typecheck` green.

---

## Open Questions

OTLP endpoint / Langfuse keys — deferred until deploy environment exists.
