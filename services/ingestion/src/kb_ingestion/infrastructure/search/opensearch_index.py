"""OpenSearch BM25 index for filing chunks."""

from __future__ import annotations

import asyncio
from typing import Any

from kb_domain import AccessionNumber, Chunk
from opensearchpy import OpenSearch, helpers


class OpenSearchChunkIndex:
    """Implements SearchIndexPort against an OpenSearch index."""

    def __init__(
        self,
        *,
        url: str = "http://localhost:9200",
        index_name: str = "kb_chunks",
        username: str | None = None,
        password: str | None = None,
        client: OpenSearch | None = None,
    ) -> None:
        self._index = index_name
        if client is not None:
            self._client = client
        else:
            user = (username or "").strip()
            secret = (password or "").strip()
            http_auth = (user, secret) if user else None
            self._client = OpenSearch(
                hosts=[url],
                http_auth=http_auth,
                use_ssl=url.startswith("https://"),
                verify_certs=False,
                ssl_show_warn=False,
            )
        self._ensure_index()


    def _ensure_index(self) -> None:
        if self._client.indices.exists(index=self._index):
            return
        self._client.indices.create(
            index=self._index,
            body={
                "settings": {"index": {"number_of_shards": 1, "number_of_replicas": 0}},
                "mappings": {
                    "properties": {
                        "chunk_id": {"type": "keyword"},
                        "accession_no": {"type": "keyword"},
                        "section": {"type": "keyword"},
                        "source_url": {"type": "keyword"},
                        "text": {"type": "text"},
                        "token_count": {"type": "integer"},
                    }
                },
            },
        )

    async def replace_chunks(
        self,
        accession_no: AccessionNumber,
        chunks: list[Chunk],
        *,
        source_url: str,
    ) -> None:
        await asyncio.to_thread(self._replace_sync, str(accession_no), chunks, source_url)

    def _replace_sync(self, accession: str, chunks: list[Chunk], source_url: str) -> None:
        self._client.delete_by_query(
            index=self._index,
            body={"query": {"term": {"accession_no": accession}}},
            refresh=True,
            conflicts="proceed",
        )
        if not chunks:
            return
        actions = [
            {
                "_index": self._index,
                "_id": chunk.chunk_id,
                "_source": {
                    "chunk_id": chunk.chunk_id,
                    "accession_no": str(chunk.accession_no),
                    "section": chunk.section,
                    "source_url": source_url,
                    "text": chunk.text,
                    "token_count": chunk.token_count,
                },
            }
            for chunk in chunks
        ]
        helpers.bulk(self._client, actions, refresh=True)

    async def search_bm25(self, query: str, *, top_k: int = 5) -> list[tuple[Chunk, float, str]]:
        return await asyncio.to_thread(self._search_sync, query, top_k)

    def _search_sync(self, query: str, top_k: int) -> list[tuple[Chunk, float, str]]:
        response: dict[str, Any] = self._client.search(
            index=self._index,
            body={
                "size": top_k,
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": ["text^2", "section"],
                    }
                },
            },
        )
        hits: list[tuple[Chunk, float, str]] = []
        for hit in response.get("hits", {}).get("hits", []):
            src = hit["_source"]
            chunk = Chunk(
                chunk_id=src["chunk_id"],
                accession_no=AccessionNumber(src["accession_no"]),
                section=src["section"],
                text=src["text"],
                token_count=int(src.get("token_count") or 0),
            )
            hits.append((chunk, float(hit.get("_score") or 0.0), str(src.get("source_url") or "")))
        return hits

    async def ping(self) -> bool:
        try:
            return bool(await asyncio.to_thread(self._client.ping))
        except Exception:  # noqa: BLE001
            return False
