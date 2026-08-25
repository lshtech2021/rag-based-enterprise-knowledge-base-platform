"""Outbound ports shared across services (Protocols only — no adapters)."""

from __future__ import annotations

from typing import Protocol


class ObjectStorePort(Protocol):
    async def put_bytes(self, key: str, body: bytes, content_type: str) -> str:
        """Store object; return canonical URI or key."""
        ...

    async def get_bytes(self, key: str) -> bytes: ...


class RelationalDbHealthPort(Protocol):
    async def ping(self) -> bool:
        """Return True if the relational database accepts connections."""
        ...
