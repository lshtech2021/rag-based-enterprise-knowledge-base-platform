# Implementation Plan: ingestion

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver `IngestFiling` end-to-end with fakes + Dagster asset graph so one fixture filing becomes chunks + embeddings.

**Architecture:** Clean Architecture in `kb-ingestion`; shared `kb_domain` entities; ports for EDGAR/store/repos/parser/embedder; in-memory adapters for tests; simple HTML section parser; HashEmbedder; Dagster definitions wrapping the pipeline.

**Tech Stack:** Python 3.12, httpx, Dagster, pytest, existing uv workspace.

**Spec:** [SPEC-ingestion.md](../SPEC-ingestion.md)

## Global Constraints

- No live SEC/OpenAI in default tests
- SEC User-Agent + ≤10 req/s on real client
- OpenSearch/Docling/financial_facts deferred
- ≤~5 files per task where practical

## Task Index

See [todo.md](todo.md) (ingestion section).

## Risks

| Risk | Mitigation |
|---|---|
| Docling weight | SimpleHtmlSectionParser behind port |
| No Docker | In-memory adapters; SQL as artifact |
| Dagster heavy in CI | Keep definitions thin; unit-test use case without running daemon |
