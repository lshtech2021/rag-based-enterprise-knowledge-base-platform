from kb_observability import setup_inmemory_tracer


def test_inmemory_tracer_records_spans() -> None:
    tracer = setup_inmemory_tracer(service_name="test-service")
    with tracer.start_span("unit.test", attributes={"ok": True}):
        pass
    spans = tracer.finished_spans()
    assert any(span.name == "unit.test" for span in spans)
