# Implementation Plan: query

> **For agentic workers:** Use subagent-driven-development or executing-plans task-by-task.

**Goal:** Grounded RAG Q&A with citations over an in-memory corpus, exposed via BFF SSE.

**Architecture:** `AnswerQuery` use case + LangGraph stages; hybrid RRF retriever; CitationValidator; FakeLLM; BFF `/v1/query`.

**Tech Stack:** Python 3.12, LangGraph, FastAPI SSE, pytest, existing `kb_domain`.

**Spec:** [SPEC-query.md](../specs/SPEC-query.md)

See [todo-query.md](todo-query.md).
