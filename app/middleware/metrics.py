"""Prometheus metrics middleware."""

from __future__ import annotations

import time

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware


REQUEST_COUNT = Counter(
    "attendance_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "attendance_http_request_latency_seconds",
    "HTTP request latency",
    ["method", "path"],
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Track basic request metrics for Prometheus scraping."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        started = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - started
        path = request.url.path
        REQUEST_COUNT.labels(request.method, path, response.status_code).inc()
        REQUEST_LATENCY.labels(request.method, path).observe(duration)
        return response


def metrics_response() -> Response:
    """Return Prometheus metrics payload."""

    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
