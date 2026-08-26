from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from kb_domain import AccessionNumber, Chunk
from kb_ingestion.infrastructure.search.opensearch_index import OpenSearchChunkIndex


@pytest.mark.asyncio
async def test_opensearch_replace_and_search() -> None:
    client = MagicMock()
    client.indices.exists.return_value = True
    bulk_calls: list[object] = []

    def fake_bulk(os_client, actions, refresh=False):  # noqa: ANN001
        bulk_calls.extend(list(actions))
        return (len(bulk_calls), [])

    index = OpenSearchChunkIndex(client=client)
    # Patch helpers.bulk used inside module
    import kb_ingestion.infrastructure.search.opensearch_index as mod

    original = mod.helpers.bulk
    mod.helpers.bulk = fake_bulk
    try:
        chunk = Chunk(
            chunk_id="acc:0",
            accession_no=AccessionNumber("0000320193-24-000123"),
            section="Item 1A",
            text="Competition risks are material.",
            token_count=8,
        )
        await index.replace_chunks(
            AccessionNumber("0000320193-24-000123"),
            [chunk],
            source_url="https://example.com",
        )
        assert client.delete_by_query.called
        assert bulk_calls

        client.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_score": 3.2,
                        "_source": {
                            "chunk_id": chunk.chunk_id,
                            "accession_no": str(chunk.accession_no),
                            "section": chunk.section,
                            "text": chunk.text,
                            "token_count": chunk.token_count,
                            "source_url": "https://example.com",
                        },
                    }
                ]
            }
        }
        hits = await index.search_bm25("competition", top_k=5)
        assert hits[0][0].chunk_id == chunk.chunk_id
        assert hits[0][2] == "https://example.com"
    finally:
        mod.helpers.bulk = original


def test_opensearch_passes_http_auth_from_config() -> None:
    with patch(
        "kb_ingestion.infrastructure.search.opensearch_index.OpenSearch"
    ) as mock_client:
        mock_client.return_value.indices.exists.return_value = True
        OpenSearchChunkIndex(
            url="https://search.example:9200",
            username="admin",
            password="s3cret",
        )
        mock_client.assert_called_once()
        kwargs = mock_client.call_args.kwargs
        assert kwargs["http_auth"] == ("admin", "s3cret")
        assert kwargs["use_ssl"] is True


def test_opensearch_skips_http_auth_when_username_empty() -> None:
    with patch(
        "kb_ingestion.infrastructure.search.opensearch_index.OpenSearch"
    ) as mock_client:
        mock_client.return_value.indices.exists.return_value = True
        OpenSearchChunkIndex(url="http://localhost:9200", username="", password="x")
        kwargs = mock_client.call_args.kwargs
        assert kwargs["http_auth"] is None
