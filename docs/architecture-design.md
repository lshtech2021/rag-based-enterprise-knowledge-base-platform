# RAG-based Enterprise Knowledge Base Platform — Architecture Design

## 1. High-Level Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                 │
│   Web UI (Next.js/React) ── Report Builder ── Chat/Query Console          │
└───────────────────────────────┬────────────────────────────────────────┘
                                 │ REST/GraphQL + WebSocket (streaming)
┌───────────────────────────────▼────────────────────────────────────────┐
│                          API GATEWAY / BFF                                │
│         FastAPI (Python) — AuthN/Z (OIDC), rate limiting, routing         │
└───────────────────────────────┬────────────────────────────────────────┘
        ┌────────────────────────┼───────────────────────────┐
        ▼                        ▼                           ▼
┌───────────────┐      ┌──────────────────┐         ┌──────────────────┐
│ Query Service  │      │ Report Service    │         │ Ingestion Service │
│ (RAG pipeline) │      │ (RAG + templating)│         │ (EDGAR fetch/ETL) │
└───────┬───────┘      └─────────┬────────┘         └─────────┬─────────┘
        │                        │                             │
        ▼                        ▼                             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATION LAYER                               │
│   LangGraph / LlamaIndex Workflows — Agents, tool-calling, retries        │
└───────────────────────────────┬────────────────────────────────────────┘
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          DATA PLANE                                       │
│  Vector DB (pgvector/Weaviate) │ Relational DB (Postgres) │ Object Store  │
│  (S3/MinIO) │ Search/BM25 (OpenSearch, hybrid retrieval) │ Cache (Redis)  │
└──────────────────────────────────────────────────────────────────────────┘
                                 ▲
┌──────────────────────────────────────────────────────────────────────────┐
│                    INGESTION / ETL PIPELINE (Airflow/Dagster)             │
│  EDGAR Full-Text/Submissions API → Parser → Chunker → Embedder → Loader   │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Clean Architecture Layering (per service)

Apply **Clean/Hexagonal Architecture** consistently across services (Ingestion, Query, Report):

```
domain/            # Entities, value objects, business rules (framework-free)
  ├─ entities: Filing, Company, Chunk, Citation, ReportTemplate
  ├─ value_objects: CIK, AccessionNumber, EmbeddingVector
  └─ services: RelevanceScorer, CitationValidator

application/        # Use cases / orchestrators (ports in/out)
  ├─ use_cases: IngestFiling, AnswerQuery, GenerateReport
  └─ ports:
       in:  IngestFilingPort, QueryPort, ReportPort
       out: FilingRepository, VectorStorePort, LLMPort, EmbedderPort

infrastructure/     # Adapters implementing ports
  ├─ edgar/: EdgarApiClient (SEC EDGAR REST)
  ├─ persistence/: PostgresFilingRepository, PgVectorStore
  ├─ llm/: OpenAIAdapter, AnthropicAdapter, LocalVLLMAdapter
  ├─ embeddings/: OpenAIEmbedder, BGEEmbedder (local)
  └─ messaging/: KafkaProducer/Consumer

presentation/        # FastAPI routers, GraphQL resolvers, CLI, gRPC
```

**Dependency Rule:** dependencies point inward (presentation → application → domain); infrastructure implements interfaces defined in `application/ports`. This makes LLM/vector-DB/embedding providers swappable without touching business logic.

---

## 3. Tech Stack (Cutting-Edge, 2025)

| Layer | Technology | Rationale |
|---|---|---|
| Frontend | **Next.js 15 (App Router) + React Server Components**, Tailwind, shadcn/ui | Streaming UI for token-by-token RAG answers |
| API Gateway | **FastAPI** + Pydantic v2, async | High-perf async I/O, OpenAPI native |
| Orchestration | **LangGraph** (stateful agent graphs) or **LlamaIndex Workflows** | Multi-step RAG, tool-calling, retries, human-in-loop |
| LLM Serving | **vLLM** (self-hosted Llama 3.1/Qwen2.5) + OpenAI/Anthropic API fallback | Cost control + flexibility; model-agnostic via port/adapter |
| Embeddings | **BGE-M3** or **text-embedding-3-large** (hybrid dense+sparse) | Multilingual, long-context financial text |
| Vector DB | **pgvector** (Postgres 16) for simplicity, or **Weaviate/Qdrant** for scale | Unified transactional + vector store reduces ops overhead |
| Hybrid Search | **OpenSearch/Elasticsearch** BM25 + vector fusion (RRF) | Financial terms/tickers need exact-match + semantic |
| Relational DB | **PostgreSQL 16** | Filings metadata, users, report templates, audit log |
| Object Storage | **S3 / MinIO** | Raw EDGAR filings (10-K/10-Q/8-K HTML/XBRL) |
| ETL Orchestration | **Dagster** (or Airflow) | Asset-based lineage for filings → chunks → embeddings |
| Streaming/Queue | **Kafka** or **Redis Streams** | Decouple ingestion from embedding workers |
| Doc Parsing | **Unstructured.io** / **Docling** for HTML/XBRL parsing | Table-aware chunking of financial statements |
| Caching | **Redis** | Query result cache, session state, semantic cache |
| Observability | **OpenTelemetry**, **Langfuse/Phoenix (Arize)** | LLM trace/eval, hallucination + latency monitoring |
| Eval | **Ragas / DeepEval** | Faithfulness, context precision/recall regression tests |
| Auth | **OIDC (Auth0/Keycloak)**, RBAC | Enterprise SSO |
| IaC/Deploy | **Kubernetes (EKS/GKE)** + **Helm**, **Terraform** | Reproducible infra |
| CI/CD | **GitHub Actions** + Argo CD (GitOps) | |

### Current local path (working demo)

Without Compose, the live demo loop is:

| Concern | Implementation |
|---|---|
| Raw filings | Local filesystem under `INGEST_DATA_DIR/raw` |
| Metadata / chunks / vectors | SQLite (`ingestion.sqlite3`); embeddings as JSON arrays |
| Embeddings | OpenAI `text-embedding-3-small` (1536-d); `HashEmbedder` in tests |
| Query | Load SQLite corpus → in-memory dense+keyword RRF; `OpenAIQueryEmbedder` + `OpenAIChatLLM` |
| Surfaces | CLI `kb-ingest`, BFF ingest/query/report, Annex `/ingest` `/console` `/reports` |
| Auth | `dev_bypass` (+ HMAC JWT stand-in labeled `oidc`) |

### Compose path (`KB_DATA_PLANE=compose`)

With `docker compose -f infra/docker-compose.yml up -d` (Postgres/pgvector + MinIO;
add `--profile opensearch` for BM25):

| Concern | Implementation |
|---|---|
| Raw filings | MinIO bucket `kb-filings` (`s3://…` URIs) |
| Metadata / chunks / vectors | Postgres 16 + pgvector (`vector(1536)` + HNSW), via `PostgresFilingRepository` + `PgVectorStore` (thin views over the pooled `PostgresKnowledgeStore`) |
| Reports | Postgres `reports` + `report_citations` (`PostgresReportRepository`) + Markdown artifact uploaded to MinIO (`s3_output_path`) |
| Query audit | `query_logs` row per answered question (`QueryLogPort`, wired to the same Postgres pool) |
| BM25 (optional) | OpenSearch index `kb_chunks`, if `OPENSEARCH_URL` is reachable |
| Query | `ComposeHybridRetriever` (pgvector dense + OpenSearch BM25 → RRF) when OpenSearch is up; `DenseOnlyRetriever` (pgvector only) otherwise |
| Schema | Applied on every connect (idempotent `CREATE TABLE/EXTENSION IF NOT EXISTS`), not only via `infra/initdb/` on a fresh volume — any reachable Postgres 16+pgvector works |
| Switch | `KB_DATA_PLANE=compose` on BFF/CLI (`--backend compose`); `local` stays SQLite+FS+in-memory reports |
| Readiness | `GET /healthz` adds `postgres_ok` / `minio_ok` / `opensearch_ok` when `data_plane=compose` |

Postgres + MinIO are required for `compose`; OpenSearch is optional (dense-only
retrieval and no BM25 indexing if it's unset or unreachable).

**Still deferred:** Docling/XBRL parsing into `financial_facts` (table exists,
stays empty), real OIDC JWKS, true LLM token SSE, Dagster-driven live ETL,
Kafka/Redis Streams messaging, Anthropic/vLLM adapters, cross-encoder rerank,
K8s/Helm.

Operator specs: [SPEC-ingestion.md](develop/specs/SPEC-ingestion.md), [SPEC-query.md](develop/specs/SPEC-query.md), [infra/README.md](../infra/README.md).

---

## 4. Ingestion Pipeline (EDGAR)

1. **Fetch** — `EdgarApiClient` calls official SEC APIs:
   - `https://data.sec.gov/submissions/CIK##########.json` (company filing index)
   - `https://www.sec.gov/Archives/edgar/data/...` (raw documents)
   - `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` (structured XBRL facts)
   - Respect SEC rate limits (10 req/sec) + required `User-Agent` header.
2. **Store raw** → S3/MinIO (immutable, versioned) + metadata row in Postgres (`filings` table: cik, accession_no, form_type, filed_date, url, s3_path).
3. **Parse** — Docling/Unstructured extracts sections (Item 1A Risk Factors, MD&A, financial tables) preserving structure; XBRL facts parsed separately into structured `financial_facts` table.
4. **Chunk** — section-aware, paragraph-first packing (~512 target / 768 max tokens, overlap), attach metadata (company, form type, fiscal period, section, source URL) for citation.
5. **Embed** — batch embedding via OpenAI (`text-embedding-3-small`); store in SQLite JSON (local) or pgvector (compose); index text in OpenSearch for BM25 when `KB_DATA_PLANE=compose`.
6. **Surfaces** — CLI `kb-ingest` (`--backend local|compose`), BFF `POST /v1/ingest` + raw download, Annex `/ingest` UI; Dagster asset graph remains for orchestration later.
7. **Dedup/Incremental** — track `last_ingested_accession` per CIK; only pull deltas via submissions API unless `force`.

---

## 5. Query (RAG) Flow

1. User submits question → Query Service (BFF `POST /v1/query` SSE).
2. **Query Understanding**: LLM rewrites/decomposes query (OpenAI chat locally; FakeLLM in tests).
3. **Hybrid Retrieval**: dense cosine + keyword RRF (local SQLite load) or **pgvector + OpenSearch BM25 → RRF** (`KB_DATA_PLANE=compose`).
4. **Re-ranking**: pass-through `NoOpReranker` *(target: cross-encoder)*.
5. **Context Assembly**: build prompt with citations (accession no., section, URL).
6. **Generation**: OpenAI chat (local demo) streams via BFF as post-hoc token SSE *(target: true token streaming / vLLM)*.
7. **Guardrails**: citation-check (`CitationValidator`) rejects ungrounded claims; online Ragas sampling deferred.
8. **Response** SSE to UI with source panel.

## 6. Report Generation Flow

1. User selects **report template** (e.g., "Quarterly Risk Summary", "Peer Comparison") + companies/period.
2. Report Service (agentic workflow via LangGraph):
   - Plans sections → issues sub-queries per section → runs RAG retrieval per section → drafts content → self-critique/refine loop → assembles final doc.
3. Output rendered to **Markdown/PDF/DOCX** (via Pandoc/WeasyPrint), stored in S3, downloadable + versioned; full provenance (citations per paragraph) retained in Postgres for audit.

---

## 7. Data Model (simplified)

```
companies(cik PK, name, ticker, sic)
filings(accession_no PK, cik FK, form_type, filed_date, period, s3_raw_path)
chunks(chunk_id PK, accession_no FK, section, text, token_count, embedding_id)
embeddings (in pgvector): chunk_id FK, vector, metadata JSONB
financial_facts(cik, concept, unit, value, fiscal_period, accn FK)  -- from XBRL
reports(report_id PK, user_id, template, params JSONB, s3_output_path, created_at)
report_citations(report_id FK, chunk_id FK, section)
query_logs(query_id, user_id, question, retrieved_chunks JSONB, answer, latency_ms)
```

---

## 8. Cross-Cutting Concerns

- **Security**: SEC data is public, but enterprise annotations/reports may be sensitive → row-level security in Postgres, encrypted S3, OIDC + RBAC.
- **Scalability**: stateless FastAPI services behind K8s HPA; async embedding workers scale independently; vector DB sharding for large corpora.
- **Testability**: domain layer is pure Python, 100% unit-testable without infra; use fakes for ports in application-layer tests.
- **Extensibility**: swapping LLM/embedding provider = new adapter behind existing port, zero change to use cases.
- **Compliance/Audit**: every generated answer/report stores full citation trail back to original EDGAR filing for regulatory defensibility.

---

Want me to go further and:
1. Scaffold the actual repo structure with this clean architecture (FastAPI + LangGraph + pgvector) and open a PR, or
2. Produce a detailed Dagster/Airflow DAG spec for the EDGAR ingestion pipeline, or
3. Draw out API contracts (OpenAPI schema) for query/report endpoints?