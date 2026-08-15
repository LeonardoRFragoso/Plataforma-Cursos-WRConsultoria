"""Structured logging configuration and request correlation middleware.

Production requirements:
- Structured JSON logs with timestamp, level, request_id
- HTTP method/path/status/latency
- Tenant identifier when available
- NEVER logs: password, JWT, MP token, TenantSecret plaintext, SMTP password

Usage in main.py:
    from app.core.logging_config import setup_logging, RequestLoggingMiddleware
    setup_logging()
    app.add_middleware(RequestLoggingMiddleware)
"""

import json
import logging
import sys
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class JSONFormatter(logging.Formatter):
    """Logs as JSON lines for production log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "tenant_id"):
            log_entry["tenant_id"] = record.tenant_id
        if hasattr(record, "method"):
            log_entry["method"] = record.method
        if hasattr(record, "path"):
            log_entry["path"] = record.path
        if hasattr(record, "status_code"):
            log_entry["status_code"] = record.status_code
        if hasattr(record, "latency_ms"):
            log_entry["latency_ms"] = record.latency_ms
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging() -> None:
    """Configure structured logging for the application."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)

    # Reduce noise from uvicorn access logs (handled by our middleware)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


logger = logging.getLogger("app.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Adds request_id to request state and logs each request.

    Generates a unique request_id per request, attaches it to
    request.state.request_id, and logs method/path/status/latency.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        # Skip logging for health checks (reduce noise)
        skip_logging = request.url.path in (
            "/health",
            "/health/live",
            "/health/ready",
            "/",
        )

        start = time.perf_counter()

        try:
            response: Response = await call_next(request)
        except Exception:
            if not skip_logging:
                latency_ms = round((time.perf_counter() - start) * 1000, 2)
                logger.error(
                    "request error",
                    extra={
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "latency_ms": latency_ms,
                    },
                )
            raise

        if not skip_logging:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            tenant_id = getattr(request.state, "tenant_id", None)
            logger.info(
                "request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                    **({"tenant_id": str(tenant_id)} if tenant_id else {}),
                },
            )

        # Echo request_id in response header
        response.headers["X-Request-ID"] = request_id
        return response
