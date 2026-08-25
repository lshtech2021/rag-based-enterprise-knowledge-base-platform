"""Observability ports."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ObservationEvent:
    kind: str
    name: str
    attributes: dict[str, Any]


@runtime_checkable
class TracerPort(Protocol):
    def start_span(
        self, name: str, *, attributes: dict[str, Any] | None = None
    ) -> AbstractContextManager[Any]:
        """Return a context manager that starts/ends a span."""
        ...


@runtime_checkable
class LlmObserverPort(Protocol):
    def record_retrieval(self, *, query: str, hit_count: int, latency_ms: float) -> None: ...

    def record_generation(
        self,
        *,
        question: str,
        answer: str,
        citation_count: int,
        latency_ms: float,
    ) -> None: ...

    def events(self) -> list[ObservationEvent]:
        """Return recorded events (test/introspection helper)."""
        ...
