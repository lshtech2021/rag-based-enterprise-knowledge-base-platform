"""Hash-based query embedder (mirrors ingestion HashEmbedder behavior)."""

from __future__ import annotations

import hashlib
import struct


class HashQueryEmbedder:
    def __init__(self, dimensions: int = 32) -> None:
        self._dimensions = dimensions

    async def embed_query(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        seed = digest
        while len(values) < self._dimensions:
            for i in range(0, len(seed) - 3, 4):
                (raw,) = struct.unpack_from(">I", seed, i)
                values.append((raw / 0xFFFFFFFF) * 2.0 - 1.0)
                if len(values) >= self._dimensions:
                    break
            seed = hashlib.sha256(seed).digest()
        norm = sum(v * v for v in values) ** 0.5 or 1.0
        return [v / norm for v in values]
