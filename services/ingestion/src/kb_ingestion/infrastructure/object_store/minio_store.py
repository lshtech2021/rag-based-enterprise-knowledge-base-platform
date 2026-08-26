"""MinIO / S3-compatible object store for raw EDGAR filings."""

from __future__ import annotations

import asyncio

from minio import Minio
from minio.error import S3Error


class MinioObjectStore:
    """Stores objects in a MinIO bucket; returns ``s3://bucket/key`` URIs."""

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str = "kb-filings",
        secure: bool = False,
        client: Minio | None = None,
    ) -> None:
        self._bucket = bucket
        host = endpoint.removeprefix("https://").removeprefix("http://")
        self._client = client or Minio(
            host,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure or endpoint.startswith("https://"),
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    async def put_bytes(self, key: str, body: bytes, content_type: str) -> str:
        cleaned = key.lstrip("/")
        await asyncio.to_thread(self._put_sync, cleaned, body, content_type)
        return f"s3://{self._bucket}/{cleaned}"

    async def get_bytes(self, key: str) -> bytes:
        cleaned = key.lstrip("/")
        if cleaned.startswith(f"{self._bucket}/"):
            cleaned = cleaned[len(self._bucket) + 1 :]
        if cleaned.startswith("s3://"):
            # s3://bucket/key
            without = cleaned.removeprefix("s3://")
            _bucket, _, path = without.partition("/")
            cleaned = path
        return await asyncio.to_thread(self._get_sync, cleaned)

    def _put_sync(self, key: str, body: bytes, content_type: str) -> None:
        from io import BytesIO

        self._client.put_object(
            self._bucket,
            key,
            BytesIO(body),
            length=len(body),
            content_type=content_type,
        )

    def _get_sync(self, key: str) -> bytes:
        try:
            response = self._client.get_object(self._bucket, key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except S3Error as exc:
            raise KeyError(key) from exc

    async def ping(self) -> bool:
        try:
            return await asyncio.to_thread(self._client.bucket_exists, self._bucket)
        except Exception:  # noqa: BLE001
            return False
