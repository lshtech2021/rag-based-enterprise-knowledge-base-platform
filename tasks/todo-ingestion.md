# Tasks: ingestion

Spec: [SPEC-ingestion.md](../SPEC-ingestion.md) · Plan: [plan-ingestion.md](plan-ingestion.md)

**Status:** Complete (2026-08-25) — MVP with in-memory adapters; live Postgres/MinIO/Docling deferred.

---

## Task 1–6: DONE

- [x] Package + schema + ports
- [x] Chunking + SimpleHtmlSectionParser
- [x] In-memory adapters + HashEmbedder
- [x] HttpEdgarClient (httpx mock + User-Agent + rate limiter)
- [x] IngestFiling use case (incl. cursor skip)
- [x] Dagster graph `raw_filing → parsed_doc → chunks → embeddings`

## Checkpoint: Complete

- [x] SPEC-ingestion success criteria (unit/application)
- [x] `make test lint typecheck` green
- [ ] Human: commit / start `query`
