"""In-memory LLM/retrieval observer (Langfuse stand-in)."""

from __future__ import annotations

from kb_observability.application.ports import LlmObserverPort, ObservationEvent


class InMemoryLlmObserver:
    def __init__(self) -> None:
        self._events: list[ObservationEvent] = []

    def record_retrieval(self, *, query: str, hit_count: int, latency_ms: float) -> None:
        self._events.append(
            ObservationEvent(
                kind="retrieval",
                name="hybrid_search",
                attributes={
                    "query": query,
                    "hit_count": hit_count,
                    "latency_ms": latency_ms,
                },
            )
        )

    def record_generation(
        self,
        *,
        question: str,
        answer: str,
        citation_count: int,
        latency_ms: float,
    ) -> None:
        self._events.append(
            ObservationEvent(
                kind="generation",
                name="answer_query",
                attributes={
                    "question": question,
                    "answer_chars": len(answer),
                    "citation_count": citation_count,
                    "latency_ms": latency_ms,
                },
            )
        )

    def events(self) -> list[ObservationEvent]:
        return list(self._events)


class NoOpLlmObserver:
    def record_retrieval(self, *, query: str, hit_count: int, latency_ms: float) -> None:
        return None

    def record_generation(
        self,
        *,
        question: str,
        answer: str,
        citation_count: int,
        latency_ms: float,
    ) -> None:
        return None

    def events(self) -> list[ObservationEvent]:
        return []


def as_observer(observer: InMemoryLlmObserver) -> LlmObserverPort:
    return observer
