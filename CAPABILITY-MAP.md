# Capability Map: RAG Enterprise Knowledge Base Platform

Source: [docs/architecture-design.md](docs/architecture-design.md)

| Module id | Responsibility | Depends on |
|---|---|---|
| platform-foundation | Monorepo, shared Python packages, Postgres/Redis/MinIO local stack, CI, Clean Architecture skeletons | — |
| identity | OIDC AuthN/Z, RBAC, session/API auth at BFF | platform-foundation |
| ingestion | EDGAR fetch → store → parse → chunk → embed → index (Dagster assets) | platform-foundation |
| query | Hybrid RAG Q&A: rewrite, retrieve, rerank, generate, cite, stream | platform-foundation, ingestion |
| report | Template-driven multi-section reports via LangGraph; export + provenance | platform-foundation, query |
| frontend | Next.js chat console, report builder, source panel, streaming UI | identity, query, report |
| observability | OpenTelemetry traces, Langfuse/Phoenix LLM eval hooks, Ragas regression | query, report |

**Build order:** `platform-foundation` → `ingestion` → `query` → `identity` → `report` → `frontend` → `observability`

**Notes:**

- **Auth decision (approved):** `identity` stays after `query`. MVP uses a **dev auth bypass** so RAG can be proven without OIDC. Production SSO lands before `frontend` hardens.
- `report` depends on `query`’s retrieval/generation ports, not on a separate duplicate RAG stack.
- Interfaces at boundaries live in the **provider** module’s future `SPEC-<id>.md` (e.g. `VectorStorePort` / `QueryPort` in `query` or shared `platform-foundation` ports package).

**Status:** Approved (umbrella + auth order). Active module: `platform-foundation` → [SPEC-platform-foundation.md](SPEC-platform-foundation.md).
