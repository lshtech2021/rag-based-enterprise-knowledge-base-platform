"""BFF OpenTelemetry request tracing middleware."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from kb_observability.application.ports import TracerPort
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class TracingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, tracer: TracerPort) -> None:
        super().__init__(app)
        self._tracer = tracer

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        attributes = {
            "http.method": request.method,
            "http.route": request.url.path,
        }
        with self._tracer.start_span("http.request", attributes=attributes):
            response = await call_next(request)
            return response
