"""Local filesystem object store for raw EDGAR filings."""

from __future__ import annotations

from pathlib import Path


class LocalFilesystemObjectStore:
    """Stores objects under ``root / key`` and returns ``file://`` URIs."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    async def put_bytes(self, key: str, body: bytes, content_type: str) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return path.resolve().as_uri()

    async def get_bytes(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def _resolve(self, key: str) -> Path:
        # Prevent path escape outside root
        cleaned = key.lstrip("/")
        path = (self._root / cleaned).resolve()
        if not str(path).startswith(str(self._root.resolve())):
            raise ValueError(f"Invalid object key: {key!r}")
        return path
