# Tasks: ingestion

Spec: [SPEC-ingestion.md](../SPEC-ingestion.md) · Plan: [plan-ingestion.md](plan-ingestion.md)

**Status:** Complete (2026-08-25) — local FS+SQLite + OpenAI embeddings + CLI/BFF/UI; Postgres/MinIO/Docling deferred.

---

## Task 1–6: DONE (MVP)

- [x] Package + schema + ports
- [x] Chunking + SimpleHtmlSectionParser
- [x] In-memory adapters + HashEmbedder
- [x] HttpEdgarClient (httpx mock + User-Agent + rate limiter)
- [x] IngestFiling use case (incl. cursor skip)
- [x] Dagster graph `raw_filing → parsed_doc → chunks → embeddings`

## Follow-on: DONE

- [x] Local filesystem object store + SQLite knowledge store
- [x] OpenAI document embedder (live) + HashEmbedder (tests)
- [x] Paragraph-aware chunking + expanded Item/Part parser
- [x] CLI `kb-ingest` (`--cik`, `--forms`, `--force`)
- [x] BFF `POST /v1/ingest` + `GET /v1/filings/{accession}/raw`
- [x] Annex `/ingest` UI with raw download

## Checkpoint

- [x] SPEC-ingestion success criteria (unit/application/BFF)
- [x] `make test lint typecheck` green
- [ ] Human: push / start deeper query↔ingest shared vector wiring
