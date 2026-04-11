"""Request context and structured request logging middleware."""

from __future__ import annotations

import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger, request_id_context


logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign request IDs and emit structured request logs."""

    def __init__(self, app, request_id_header: str) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.request_id_header = request_id_header

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get(self.request_id_header) or str(uuid.uuid4())
        token = request_id_context.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.info(
                "request_completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": getattr(locals().get("response"), "status_code", 500),
                    "duration_ms": duration_ms,
                },
            )
            request_id_context.reset(token)

        response.headers[self.request_id_header] = request_id
        return response
