"""BFF OpenTelemetry request tracing middleware + access logs."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from kb_observability.application.ports import TracerPort
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from kb_bff.logging_utils import get_logger, log_event

_log = get_logger("kb_bff.http")


class TracingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, tracer: TracerPort) -> None:
        super().__init__(app)
        self._tracer = tracer

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        method = request.method
        access_level = logging.DEBUG if path == "/healthz" else logging.INFO
        attributes = {
            "http.method": method,
            "http.route": path,
        }
        log_event(_log, access_level, "http.request.start", method=method, path=path)
        started = time.perf_counter()
        try:
            with self._tracer.start_span("http.request", attributes=attributes):
                response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            log_event(
                _log,
                logging.ERROR,
                "http.request.error",
                method=method,
                path=path,
                duration_ms=round(duration_ms, 1),
            )
            raise
        duration_ms = (time.perf_counter() - started) * 1000
        log_event(
            _log,
            access_level,
            "http.request.end",
            method=method,
            path=path,
            status=response.status_code,
            duration_ms=round(duration_ms, 1),
        )
        return response
