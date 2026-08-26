# Todo: Compose data plane + config selection

**Plan:** [plan-compose-data-plane.md](plan-compose-data-plane.md)  
**Status:** Done

- [x] Complete §7 Postgres schema in initdb + migrate-on-connect (`financial_facts`, `reports`, `report_citations`, `query_logs`)
- [x] Finish compose ingest/query/report wiring: Postgres+pgvector + MinIO (+ OpenSearch when URL set)
- [x] Single config `KB_DATA_PLANE=local|compose`; document in `.env.example` + BFF settings + CLI
- [x] When compose: Postgres reports + MinIO artifacts + `query_logs` writes
- [x] Expose `PostgresFilingRepository` + `PgVectorStore` (split or aliases)
- [x] Healthz flags + README/architecture: how to select local vs compose
