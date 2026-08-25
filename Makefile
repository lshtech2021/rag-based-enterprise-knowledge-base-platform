.PHONY: test lint typecheck ingest

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy

# Usage: make ingest CIK=320193 FORMS=10-K,10-Q
# Requires SEC_USER_AGENT and OPENAI_API_KEY
FORMS ?= 10-K,10-Q,8-K
ingest:
	@test -n "$(CIK)" || (echo "Set CIK=... e.g. make ingest CIK=320193"; exit 2)
	@test -n "$${SEC_USER_AGENT}" || (echo "Set SEC_USER_AGENT with contact email"; exit 2)
	@test -n "$${OPENAI_API_KEY}" || (echo "Set OPENAI_API_KEY for embeddings"; exit 2)
	uv run kb-ingest --cik "$(CIK)" --backend local --forms "$(FORMS)"
