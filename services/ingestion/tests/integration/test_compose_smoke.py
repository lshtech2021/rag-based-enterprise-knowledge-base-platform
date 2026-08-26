"""Optional Compose integration tests — skipped unless KB_RUN_COMPOSE_TESTS=1."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


def _enabled() -> bool:
    return os.environ.get("KB_RUN_COMPOSE_TESTS", "").strip() == "1"


@pytest.mark.asyncio
@pytest.mark.skipif(not _enabled(), reason="Set KB_RUN_COMPOSE_TESTS=1 with Compose up")
async def test_compose_postgres_ping() -> None:
    from kb_ingestion.infrastructure.persistence.postgres_store import PostgresKnowledgeStore

    url = os.environ.get("DATABASE_URL", "postgresql://kb:kb@localhost:5432/knowledge_base")
    store = await PostgresKnowledgeStore.connect(url)
    try:
        assert await store.ping() is True
    finally:
        await store.aclose()
