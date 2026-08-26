# Report service

Template-driven multi-section reports over grounded RAG.

Spec: [`SPEC-report.md`](../../SPEC-report.md)

## Persistence

Selected by the BFF's `KB_DATA_PLANE` (see [infra/README.md](../../infra/README.md)):

| `KB_DATA_PLANE` | Repository | Markdown artifact |
|---|---|---|
| `local` (default) | `InMemoryReportRepository` | none (in-process only) |
| `compose` | `PostgresReportRepository` (`reports` + `report_citations`) | uploaded to MinIO, `s3_output_path` recorded |

`PostgresReportRepository.connect(database_url)` applies its schema
idempotently on every connect, so it also works against a Postgres you
provisioned yourself (not only a fresh `docker compose` volume).
