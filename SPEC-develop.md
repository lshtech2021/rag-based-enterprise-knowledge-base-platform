# Spec: Develop — RAG Enterprise Knowledge Base Platform

Living develop spec for building the platform described in [docs/architecture-design.md](docs/architecture-design.md). Module boundaries and build order are indexed by [CAPABILITY-MAP.md](CAPABILITY-MAP.md). This document is the **umbrella** develop contract (shared stack, layout, style, tests, boundaries). Each module later gets `SPEC-<module-id>.md` after the map is approved.

---

## ASSUMPTIONS I'M MAKING

Correct these before Plan / Tasks / Implement, or they become the locked defaults:

1. **Monorepo** — Python services + Next.js frontend in one repo (not polyrepo).
2. **Orchestration** — **LangGraph** (not LlamaIndex Workflows) for query agents and report workflows.
3. **Vector store** — **pgvector on PostgreSQL 16** for MVP (not Weaviate/Qdrant yet).
4. **Hybrid search** — **OpenSearch** BM25 + vector fusion via RRF; can be stubbed behind a port until ingestion indexes text.
5. **ETL** — **Dagster** (not Airflow) for EDGAR asset lineage.
6. **Queue** — **Redis Streams** for MVP decoupling (not Kafka).
7. **LLM** — OpenAI/Anthropic API adapters first; **vLLM** adapter interface exists but self-hosted serving is post-MVP.
8. **Embeddings** — OpenAI `text-embedding-3-large` first; BGE-M3 as a second adapter.
9. **Parsing** — **Docling** preferred for HTML/XBRL-aware section extraction.
10. **Auth timing (approved)** — MVP query/ingestion run with a **dev auth bypass**; OIDC (Keycloak or Auth0) before frontend production hardening. `identity` follows `query` in the capability map.
11. **API surface** — REST + SSE streaming for answers first; GraphQL and WebSocket deferred.
12. **Deploy target for develop** — Docker Compose local; Kubernetes/Helm/Terraform are later infra work, not required for module MVP success.
13. **Primary domain** — SEC EDGAR 10-K / 10-Q / 8-K for a curated company set (not “all of EDGAR” on day one).

→ **Approved** (2026-08-25) with dev auth bypass. Assumptions above are locked defaults.

---

## Objective

Build an enterprise knowledge base that ingests SEC EDGAR filings, answers grounded questions with citations, and generates auditable multi-section reports.

**Users**

- Analyst / researcher: ask questions, inspect sources, export reports.
- Platform operator: run ingestion, monitor lineage and evals.
- Enterprise admin (later): SSO, RBAC, audit.

**Success looks like**

- A filing for a known CIK can be ingested end-to-end into Postgres + pgvector (+ OpenSearch when enabled).
- A question about that filing returns a streamed answer with verifiable citations (accession, section, URL).
- A report template run produces a versioned artifact (Markdown first) with per-section provenance.
- Domain and application layers are testable without live LLM / EDGAR / vector infra (fakes behind ports).

---

## Tech Stack

| Area | Choice (MVP) | Version / notes |
|---|---|---|
| Language (services) | Python 3.12+ | uv or poetry for deps |
| API / BFF | FastAPI + Pydantic v2 | Async; OpenAPI generated |
| Frontend | Next.js 15 App Router + React + Tailwind + shadcn/ui | SSE client for streaming |
| Orchestration | LangGraph | Query + report graphs |
| DB | PostgreSQL 16 + pgvector | Metadata + vectors |
| Search | OpenSearch | BM25; hybrid RRF |
| Object store | MinIO (S3 API) | Raw filings |
| Cache / streams | Redis | Cache + Redis Streams |
| ETL | Dagster | Asset graph |
| Parsing | Docling | Section-aware |
| LLM / embed | OpenAI (Anthropic optional) | Ports for swap |
| Auth | OIDC (Keycloak local) | After query MVP |
| Observability | OpenTelemetry + Langfuse or Phoenix | After query/report |
| Eval | Ragas / DeepEval | Offline regression in CI later |
| IaC | Docker Compose first | K8s/Helm/TF later |

---

## Commands

Exact commands may be finalized in `platform-foundation`; until then these are the **target** developer interface:

```bash
# Local infra
docker compose up -d                  # Postgres+pgvector, Redis, MinIO, OpenSearch

# Python (from repo root / services workspace)
uv sync                               # or: poetry install
uv run pytest                         # unit + application tests
uv run pytest --cov=src --cov-fail-under=80   # domain/application coverage gate (tune per module)
uv run ruff check --fix .
uv run ruff format .
uv run mypy src
uv run uvicorn apps.bff.main:app --reload --port 8000

# Dagster (ingestion)
uv run dagster dev -f services/ingestion/definitions.py

# Frontend
cd apps/web && npm install && npm run dev
cd apps/web && npm run lint && npm run test && npm run build

# Quality gates (CI mirrors these)
make test                             # all Python + web unit tests
make lint
make typecheck
```

---

## Project Structure

```
/
├── CAPABILITY-MAP.md
├── SPEC-develop.md              # this file (umbrella)
├── SPEC-<module-id>.md          # per-module specs (after map approval)
├── docs/
│   └── architecture-design.md
├── apps/
│   ├── bff/                     # FastAPI gateway: auth, routing, rate limits
│   └── web/                     # Next.js UI
├── services/
│   ├── ingestion/               # EDGAR ETL + Dagster
│   ├── query/                   # RAG pipeline
│   └── report/                  # Report LangGraph workflows
├── packages/                    # shared libraries (Python)
│   ├── domain/                  # entities, VOs, domain services (framework-free)
│   ├── application/             # shared ports if truly cross-service; else keep per service
│   └── testing/                 # fakes, factories
├── infra/
│   ├── docker-compose.yml
│   └── (later) terraform/, helm/
├── tasks/                       # plan.md, todo.md after Spec approval
└── tests/                       # cross-cutting / contract tests (optional)
```

**Per-service Clean Architecture** (Ingestion, Query, Report):

```
services/<name>/
  domain/
  application/          # use_cases/, ports/in/, ports/out/
  infrastructure/       # edgar/, persistence/, llm/, embeddings/, messaging/
  presentation/         # FastAPI routers, Dagster defs, CLI
  tests/
    unit/               # domain + use cases with fakes
    integration/        # marked; need Compose
```

**Dependency rule:** presentation → application → domain; infrastructure implements `application/ports`.

---

## Code Style

**Python**

- Packages/modules: `snake_case`; classes: `PascalCase`; functions: `snake_case`.
- Ports are protocols/ABCs in `application/ports`; adapters never imported from domain/application.
- Prefer explicit types; Pydantic models at presentation and adapter edges only.
- No LLM/HTTP/DB calls inside `domain/`.

```python
# Good: use case depends on ports, not concrete clients
class AnswerQuery:
    def __init__(
        self,
        retriever: HybridRetrieverPort,
        llm: LLMPort,
        citations: CitationValidator,
    ) -> None: ...

    async def execute(self, command: AnswerQueryCommand) -> AnswerQueryResult:
        rewritten = await self.llm.rewrite(command.question)
        hits = await self.retriever.search(rewritten, filters=command.filters)
        draft = await self.llm.generate(question=command.question, contexts=hits)
        return self.citations.validate(draft, hits)
```

**TypeScript (web)**

- App Router; Server Components by default; client only for streaming chat and interactive report builder.
- Colocate feature folders under `app/` / `components/`; no business RAG logic in the browser beyond display.

**Formatting**

- Python: Ruff format + Ruff lint; mypy strict on domain/application.
- Web: ESLint + Prettier (or Biome if chosen in foundation).

---

## Testing Strategy

| Level | Where | What |
|---|---|---|
| Unit | `services/*/tests/unit`, `packages/*/tests` | Domain rules, use cases with fakes (no network) |
| Contract | adapter tests with Testcontainers/Compose | Postgres/pgvector, Redis, MinIO |
| Eval | `tests/eval` (later) | Ragas faithfulness / context precision on golden Q&A set |
| E2E | Playwright (later, with `frontend`) | Chat ask → streamed answer → source panel |

**Expectations**

- Domain + application: high coverage; CI fails if use-case tests hit real APIs.
- Integration tests: opt-in marker `@pytest.mark.integration`; required in CI when Compose services available.
- Never delete or skip failing tests without approval (see Boundaries).

---

## Boundaries

**Always**

- Keep dependency rule (inward-only); new infra = new adapter behind an existing or newly approved port.
- Respect SEC EDGAR rate limits (≤10 req/s) and required `User-Agent`.
- Persist citation/provenance for every generated answer and report section.
- Run unit tests for touched modules before committing.
- Update this spec (or the relevant `SPEC-<id>.md`) when behavior or data model changes.

**Ask first**

- Adding a dependency (LLM provider, DB, queue, UI kit).
- Schema migrations that change `companies` / `filings` / `chunks` / `reports` contracts.
- Switching stack defaults locked in Assumptions (e.g. Weaviate instead of pgvector).
- Changing public HTTP API shapes once published.
- Introducing Kafka, GraphQL, or K8s before the Compose MVP path is green.

**Never**

- Commit secrets, API keys, or real OIDC client secrets.
- Call external LLMs or EDGAR from domain unit tests.
- Store generated answers without a citation trail.
- Bypass rate limiting against SEC in shared/dev automation without an explicit throttle.
- Expand to “full EDGAR universe” without an approved ingestion capacity plan.

---

## Data Model (MVP)

Aligned with architecture design; implement via migrations in `platform-foundation` / `ingestion`:

- `companies(cik PK, name, ticker, sic)`
- `filings(accession_no PK, cik FK, form_type, filed_date, period, s3_raw_path)`
- `chunks(chunk_id PK, accession_no FK, section, text, token_count, embedding_id)`
- embeddings in pgvector keyed by `chunk_id`
- `financial_facts(...)` from XBRL (can lag first HTML/text path)
- `reports`, `report_citations`, `query_logs` with `query` / `report` modules

---

## MVP Success Criteria (umbrella)

Testable “develop is on track” gates — detailed criteria move into per-module specs:

1. **Compose stack** boots: Postgres+pgvector, Redis, MinIO (OpenSearch optional flag).
2. **Ingest one 10-K** for a fixture CIK → raw in MinIO, row in `filings`, chunks + vectors queryable.
3. **Answer one golden question** with ≥1 valid citation pointing at accession + section; stream over SSE.
4. **CitationValidator** rejects a deliberately ungrounded draft in unit tests.
5. **Report skeleton** runs one template with ≥2 sections, each with provenance rows (Markdown export sufficient).
6. **Clean Architecture** enforced: swapping `LLMPort` fake ↔ OpenAI adapter requires no domain changes.
7. Specs committed: this file + approved `CAPABILITY-MAP.md`; module specs exist for any module under active implementation.

---

## Module Spec Index

| Module id | Spec file | Status |
|---|---|---|
| platform-foundation | `SPEC-platform-foundation.md` | Implemented (scaffold) |
| ingestion | `SPEC-ingestion.md` | Implemented (MVP with fakes) |
| query | `SPEC-query.md` | Implemented (MVP with fakes + SSE) |
| identity | `SPEC-identity.md` | Implemented (dev_bypass + HMAC JWT oidc stand-in) |
| report | `SPEC-report.md` | Implemented (Markdown MVP + provenance) |
| frontend | `SPEC-frontend.md` | Implemented (Annex Next.js MVP) |
| observability | `SPEC-observability.md` | Implemented (OTel + observer + citation eval) |

After map + this umbrella are approved: Specify → Plan → Tasks → Implement **per module** in build order, starting with `platform-foundation`.

---

## Open Questions

1. Prefer **Auth0** or self-hosted **Keycloak** for OIDC? (only needed when `identity` starts)
2. Is **SSE** acceptable for streaming, or is WebSocket required for v1 UI?
3. Curated company list for MVP — how many CIKs / which tickers?
4. Should `packages/domain` be a single shared domain package, or duplicated-per-service domains to avoid a ball-of-mud?

**Resolved**

- Auth after query + **dev auth bypass** for faster RAG proof — approved.

---

## Out of Scope (this develop umbrella)

- Production Kubernetes / Terraform / Argo CD hardening
- Full GraphQL API
- Kafka migration
- Self-hosted vLLM cluster operations
- Legal/compliance sign-off beyond technical citation trails
