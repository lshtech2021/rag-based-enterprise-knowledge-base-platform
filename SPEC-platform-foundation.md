# Spec: platform-foundation

Module id: `platform-foundation`  
Depends on: —  
Umbrella: [SPEC-develop.md](SPEC-develop.md) · Map: [CAPABILITY-MAP.md](CAPABILITY-MAP.md)  
**Status:** Implemented (scaffold complete; Compose not runtime-verified in this environment — Docker unavailable)

---

## Objective

Scaffold the monorepo so later modules (`ingestion`, `query`, …) share one local data plane, one Python tooling story, and Clean Architecture skeletons—without implementing EDGAR, RAG, or OIDC yet.

**User:** platform engineer / agent implementing the next modules.

**Success:** `docker compose up -d` yields healthy Postgres+pgvector, Redis, MinIO; `uv sync && uv run pytest` passes on shared domain stubs; BFF health endpoint responds with **dev auth bypass**; CI runs lint/typecheck/unit tests.

---

## Tech Stack

- Python 3.12+, **uv** workspace
- FastAPI + Pydantic v2 (minimal BFF)
- PostgreSQL 16 + pgvector, Redis, MinIO via Docker Compose
- OpenSearch **optional** profile (stub port OK if not up)
- Ruff, mypy, pytest
- GitHub Actions: lint + typecheck + unit tests (no full Compose required in CI for this module)

---

## Commands

```bash
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml ps   # healthy postgres, redis, minio

uv sync
uv run pytest
uv run ruff check --fix .
uv run ruff format .
uv run mypy packages services/apps  # as packages land
uv run uvicorn apps.bff.main:app --reload --port 8000
curl -s localhost:8000/healthz      # 200, includes auth_mode=dev_bypass

make test && make lint && make typecheck
```

---

## Project Structure (this module creates)

```
/
├── pyproject.toml              # uv workspace root
├── Makefile
├── .github/workflows/ci.yml
├── infra/
│   ├── docker-compose.yml      # postgres+pgvector, redis, minio; opensearch profile
│   └── initdb/                 # optional pgvector extension SQL
├── packages/
│   ├── domain/                 # shared entities/VOs (Filing, Company, Chunk, Citation stubs)
│   ├── application_ports/      # shared outbound port Protocols (minimal)
│   └── testing/                # factories / fakes helpers
├── apps/
│   └── bff/
│       ├── main.py
│       └── presentation/       # /healthz, dev bypass middleware stub
├── services/
│   ├── ingestion/              # empty Clean Architecture dirs + README
│   ├── query/
│   └── report/
└── tests/                      # workspace-level smoke if needed
```

---

## Code Style

Same as umbrella: ports as `Protocol`, no infra imports in domain, Ruff + mypy on `packages/` and `apps/bff`.

```python
# packages/domain/src/kb_domain/value_objects.py
from typing import NewType

CIK = NewType("CIK", str)
AccessionNumber = NewType("AccessionNumber", str)
```

---

## Testing Strategy

- Unit: domain value-object validation (e.g. CIK zero-padding rules) in `packages/domain`
- Smoke: BFF `/healthz` TestClient test with `auth_mode=dev_bypass`
- No integration requirement against Compose for CI green; document manual Compose check in success criteria

---

## Boundaries

**Always**

- Keep service skeletons empty of business use cases (those land in later module specs).
- Document `AUTH_MODE=dev_bypass` as default in Compose/BFF env sample.
- Single uv workspace; no per-service poetry lock drift.

**Ask first**

- Adding Kafka, OpenSearch-as-required, or K8s manifests.
- Moving shared domain into per-service packages instead.

**Never**

- Real OIDC client secrets in repo.
- Embedding EDGAR/LLM client code in this module’s “done” criteria.

---

## Success Criteria

1. Compose: Postgres (pgvector enabled), Redis, MinIO healthy.
2. `uv sync` + `uv run pytest` green on domain + BFF health tests.
3. `GET /healthz` → 200 JSON including `"auth_mode": "dev_bypass"`.
4. Service directories exist with `domain/`, `application/`, `infrastructure/`, `presentation/` placeholders.
5. CI workflow runs ruff, mypy, pytest on PR.
6. Makefile targets: `test`, `lint`, `typecheck` match umbrella commands.

---

## Open Questions

None blocking — Auth0 vs Keycloak deferred to `identity`. Shared vs per-service domain: **shared stubs in `packages/domain`** for Company/Filing/Chunk/Citation (decision for this module).
