"""Deterministic hash-based embedder for tests and offline MVP."""

from __future__ import annotations

import hashlib
import struct


class HashEmbedder:
    def __init__(self, dimensions: int = 32) -> None:
        if dimensions < 8:
            raise ValueError("dimensions must be >= 8")
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
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
        # L2 normalize
        norm = sum(v * v for v in values) ** 0.5 or 1.0
        return [v / norm for v in values]
