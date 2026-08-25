import pytest
from kb_ingestion.infrastructure.embeddings.hash_embedder import HashEmbedder


@pytest.mark.asyncio
async def test_hash_embedder_is_deterministic_and_normalized() -> None:
    embedder = HashEmbedder(dimensions=16)
    a = (await embedder.embed_documents(["hello"]))[0]
    b = (await embedder.embed_documents(["hello"]))[0]
    c = (await embedder.embed_documents(["world"]))[0]
    assert a == b
    assert a != c
    assert len(a) == 16
    assert abs(sum(x * x for x in a) - 1.0) < 1e-6
