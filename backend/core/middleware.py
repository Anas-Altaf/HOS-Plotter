"""Request ID + access logging middleware."""
from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar

_request_id: ContextVar[str] = ContextVar("request_id", default="-")

logger = logging.getLogger("access")


def get_request_id() -> str:
    return _request_id.get()


class RequestIdFilter(logging.Filter):
    """Inject the current request_id into every LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


class RequestIdMiddleware:
    """Generate a short request id, attach to context + response header, log access."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:8]
        token = _request_id.set(rid)
        start = time.perf_counter()
        try:
            response = self.get_response(request)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            _request_id.reset(token)

        try:
            response["X-Request-Id"] = rid
        except Exception:
            pass

        logger.info(
            "%s %s -> %s %.1fms",
            request.method,
            request.get_full_path(),
            getattr(response, "status_code", "?"),
            elapsed_ms,
        )
        return response
