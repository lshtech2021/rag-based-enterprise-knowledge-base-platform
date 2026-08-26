from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock

import pytest
from kb_ingestion.infrastructure.object_store.minio_store import MinioObjectStore


@pytest.mark.asyncio
async def test_minio_put_and_get_bytes() -> None:
    client = MagicMock()
    client.bucket_exists.return_value = True
    stored: dict[str, bytes] = {}

    def put_object(bucket, key, data, length, content_type):  # noqa: ANN001
        stored[key] = data.read() if hasattr(data, "read") else data

    def get_object(bucket, key):  # noqa: ANN001
        response = MagicMock()
        response.read.return_value = stored[key]
        return response

    client.put_object.side_effect = put_object
    client.get_object.side_effect = get_object

    store = MinioObjectStore(
        endpoint="localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="kb-filings",
        client=client,
    )
    uri = await store.put_bytes("filings/a.htm", b"<html/>", "text/html")
    assert uri == "s3://kb-filings/filings/a.htm"
    assert await store.get_bytes(uri) == b"<html/>"
    assert isinstance(BytesIO(b""), BytesIO)
