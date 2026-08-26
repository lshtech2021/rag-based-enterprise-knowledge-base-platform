# Spec: report

Module id: `report`  
Depends on: `platform-foundation`, `query`  
Umbrella: [SPEC-develop.md](SPEC-develop.md) · Map: [CAPABILITY-MAP.md](CAPABILITY-MAP.md)  
Architecture: [docs/architecture-design.md](../../architecture-design.md) §6

---

## Objective

Generate multi-section, **citation-backed** reports from templates by running grounded RAG sub-queries per section, assembling Markdown, and retaining per-section provenance.

**User:** analyst (RBAC role `analyst`) via BFF.

**MVP success:** Template `quarterly_risk_summary` (≥2 sections) → `GenerateReport` produces Markdown with headings + `[cite:…]` markers, persists report + `report_citations`, exposes `POST /v1/reports` and `GET /v1/reports/{id}`; tests use fakes / in-memory store (no S3/PDF).

---

## Tech Stack

| Piece | Choice |
|---|---|
| Package | `kb-report` under `services/report` |
| RAG | `SectionAnswerPort` wrapping `AnswerQuery` (no duplicate RAG stack) |
| Orchestration | LangGraph graph entrypoint (plan → fill sections → assemble) |
| Output | Markdown only (PDF/DOCX/Pandoc deferred) |
| Persist | `local`: in-memory repository. `compose`: `PostgresReportRepository` (Postgres `reports`/`report_citations` + Markdown artifact in MinIO) |

---

## Commands

```bash
uv sync --group dev
uv run pytest services/report apps/bff -q
make test lint typecheck
```

---

## Project Structure

```
services/report/
  src/kb_report/
    domain/templates.py
    application/ports.py
    application/use_cases/generate_report.py
    infrastructure/in_memory_report_store.py
    infrastructure/postgres_report_store.py
    infrastructure/answer_query_adapter.py
    presentation/graph.py
  tests/
apps/bff/report_router.py
```

---

## Testing Strategy

- Unit: template resolves ≥2 section prompts; Markdown assembler includes headings
- Application: GenerateReport with fake SectionAnswerPort → citations persisted per section
- BFF: POST creates report; GET returns markdown + citations; requires analyst

---

## Boundaries

**Always:** Provenance per section (chunk_id, accession, section name, source_url); reuse query grounding (no uncited generation path).

**Ask first:** Adding PDF/DOCX rendering deps; changing template ids once UI depends on them.

**Never:** Generate report content without going through SectionAnswerPort / citation trail.

---

## Success Criteria

1. Built-in template has ≥2 sections with distinct query prompts.
2. GenerateReport returns markdown containing both section titles and at least one cite marker.
3. Stored report lists citations linked to section ids.
4. LangGraph compiles and runs the report pipeline.
5. `POST /v1/reports` + `GET /v1/reports/{id}` work under `dev_bypass`.
6. `make test lint typecheck` green offline.

---

## Open Questions

None blocking. S3 versioning of report artifacts (beyond the single MinIO
upload per save) remains deferred.
