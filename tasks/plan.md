# Implementation Plan: platform-foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the monorepo, local data plane, shared Python packages, BFF health + dev auth bypass, and CI—so `ingestion` can start next.

**Architecture:** uv workspace monorepo; Clean Architecture directory skeletons per service; Docker Compose for Postgres+pgvector, Redis, MinIO; FastAPI BFF with `AUTH_MODE=dev_bypass` only (no OIDC).

**Tech Stack:** Python 3.12+, uv, FastAPI, Pydantic v2, Ruff, mypy, pytest, Docker Compose, GitHub Actions.

**Spec:** [SPEC-platform-foundation.md](../SPEC-platform-foundation.md) · Umbrella: [SPEC-develop.md](../SPEC-develop.md)

## Global Constraints

- Python 3.12+; uv workspace (not poetry)
- Dev auth bypass default; no OIDC in this module
- Domain stays framework-free; no EDGAR/LLM business logic here
- Tasks ≤ ~5 files each; TDD where behavior exists
- Do not implement ingestion/query/report use cases

## Architecture Decisions

- **uv workspace** at repo root with `packages/*` and `apps/bff` as members.
- **Shared domain stubs** in `packages/domain` for cross-service entities; services get empty layer dirs only.
- **OpenSearch** behind Compose profile `opensearch` (optional); not required for foundation green.
- **CI without Compose** — unit/lint/typecheck only; Compose verified manually / later integration job.

## Dependency Graph

```
Docker Compose (postgres, redis, minio)
        │
uv workspace + tool config (ruff, mypy, pytest)
        │
packages/domain (CIK, AccessionNumber, entity stubs)
        │
packages/testing + packages/application_ports (minimal Protocols)
        │
apps/bff (/healthz + AUTH_MODE=dev_bypass)
        │
service skeletons + Makefile + CI
```

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| pgvector image mismatch | Med | Use well-known `pgvector/pgvector:pg16` image; init SQL `CREATE EXTENSION` |
| uv workspace layout unfamiliar | Low | Follow Astral uv workspace docs; single root lockfile |
| Scope creep into ingestion | High | Success criteria exclude EDGAR/LLM; refuse in review |

## Parallelization

- After Task 1 (Compose): Tasks 2–3 sequential (tooling then domain).
- Task 4 (ports/testing) can follow domain immediately.
- Task 5 (BFF) after ports stub.
- Task 6 (skeletons + Makefile + CI) after BFF health test exists.

## Verification Checkpoints

- After Tasks 1–3: Compose healthy; pytest collects domain tests.
- After Tasks 4–5: `/healthz` test green; curl works with Compose up.
- After Task 6: `make test lint typecheck` green; CI file present.

## Task List Index

See [tasks/todo.md](todo.md) for acceptance criteria and file lists.

## Open Questions

None for foundation. Proceed to Implement only after human approves this plan + todo.
