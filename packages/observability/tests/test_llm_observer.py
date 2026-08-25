from kb_observability import InMemoryLlmObserver


def test_inmemory_observer_records_retrieval_and_generation() -> None:
    observer = InMemoryLlmObserver()
    observer.record_retrieval(query="risks?", hit_count=2, latency_ms=12.5)
    observer.record_generation(
        question="risks?",
        answer="Competition is material [cite:c1]",
        citation_count=1,
        latency_ms=40.0,
    )
    kinds = [event.kind for event in observer.events()]
    assert kinds == ["retrieval", "generation"]
