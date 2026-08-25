"""OpenTelemetry tracer factory with in-memory exporter for tests."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.util.types import AttributeValue


class OtelTracer:
    def __init__(self, provider: TracerProvider, exporter: InMemorySpanExporter) -> None:
        self._provider = provider
        self._tracer = provider.get_tracer("kb-observability")
        self.exporter = exporter

    def start_span(
        self, name: str, *, attributes: dict[str, AttributeValue] | None = None
    ) -> AbstractContextManager[Any]:
        return self._tracer.start_as_current_span(name, attributes=attributes or {})

    def finished_spans(self) -> list[Any]:
        self._provider.force_flush()
        return list(self.exporter.get_finished_spans())


def setup_inmemory_tracer(service_name: str = "kb-bff") -> OtelTracer:
    """Create an isolated TracerProvider (no global override) with in-memory export."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return OtelTracer(provider, exporter)
