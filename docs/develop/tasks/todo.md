# Tasks: platform-foundation

Spec: [SPEC-platform-foundation.md](../specs/SPEC-platform-foundation.md) · Plan: [plan.md](plan.md)

**Status:** Complete (2026-08-25). Compose files present; runtime Compose check skipped (no Docker in build host).

---

## Task 1: Local data plane (Docker Compose) — DONE

**Acceptance:**
- [x] Compose file starts postgres, redis, minio (manual when Docker available)
- [x] Postgres init enables `vector` extension
- [x] OpenSearch only with `--profile opensearch`

**Files:** `infra/docker-compose.yml`, `infra/initdb/01-pgvector.sql`, `infra/README.md`

---

## Task 2: uv workspace + quality tooling — DONE

**Acceptance:**
- [x] `uv sync` succeeds
- [x] `uv run ruff check .` and `uv run pytest` runnable

**Files:** `pyproject.toml`, `.python-version`, `.gitignore`

---

## Checkpoint: After Tasks 1–2 — DONE

---

## Task 3: Shared domain package stubs — DONE

**Acceptance:**
- [x] Importable as `kb_domain`
- [x] Invalid CIK rejected in unit tests
- [x] No FastAPI/SQLAlchemy imports in domain

**Verify:** `uv run pytest packages/domain -q` — pass

---

## Task 4: Shared ports + testing helpers — DONE

**Acceptance:**
- [x] Protocols importable; no concrete clients
- [x] Factory builds valid `Filing` stub

---

## Task 5: BFF health + dev auth bypass — DONE

**Acceptance:**
- [x] Default `auth_mode` is `dev_bypass`
- [x] TestClient asserts 200 + JSON shape
- [x] No OIDC dependency

**Verify:** tests + `curl localhost:8000/healthz` → `{"status":"ok","auth_mode":"dev_bypass"}`

---

## Checkpoint: After Tasks 3–5 — DONE

---

## Task 6a: Service Clean Architecture skeletons — DONE

**Acceptance:**
- [x] Layer dirs under ingestion, query, report
- [x] Service READMEs point to future specs

---

## Task 6b: Makefile + GitHub Actions — DONE

**Acceptance:**
- [x] `make test`, `make lint`, `make typecheck`
- [x] CI workflow present

---

## Checkpoint: Complete (platform-foundation) — DONE

- [x] SPEC success criteria met (Compose runtime pending Docker host)
- [x] No EDGAR/LLM/OIDC implementation
- [ ] Human approves → next: `SPEC-ingestion.md` + plan
