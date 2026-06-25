"""Structured JSON logging for production observability.

Provides:
- JSON-formatted log output for log aggregation (ELK, Datadog, etc.)
- Request-scoped context (trace_id, tenant_id, user_id)
- Performance logging for LLM calls and retrieval
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import UTC, datetime
from typing import Any


class JSONFormatter(logging.Formatter):
    """JSON log formatter for production logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add trace context if available
        if hasattr(record, "trace_id"):
            log_entry["trace_id"] = record.trace_id
        if hasattr(record, "tenant_id"):
            log_entry["tenant_id"] = record.tenant_id

        # Add performance data if available
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        if hasattr(record, "model"):
            log_entry["model"] = record.model
        if hasattr(record, "cost_usd"):
            log_entry["cost_usd"] = record.cost_usd

        # Add exception info
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        for key in ("status_code", "method", "path", "tenant_id", "trace_id",
                     "duration_ms", "model", "cost_usd", "tokens_in", "tokens_out"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        return json.dumps(log_entry, default=str)


class PerformanceFilter(logging.Filter):
    """Filter that adds performance context to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        return True


def setup_structured_logging(level: str = "INFO") -> None:
    """Configure structured JSON logging for production.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    root.handlers.clear()

    # JSON handler (stdout)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)

    # Also keep a human-readable handler for development
    if level.upper() == "DEBUG":
        debug_handler = logging.StreamHandler(sys.stderr)
        debug_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"
        ))
        root.addHandler(debug_handler)

    logging.info(f"Structured logging initialized (level={level})")


class RequestLogger:
    """Request-scoped logger with trace context."""

    def __init__(self, trace_id: str = "", tenant_id: str = ""):
        self.trace_id = trace_id
        self.tenant_id = tenant_id
        self._start_time = 0.0

    def start(self) -> None:
        """Mark request start."""
        self._start_time = time.perf_counter()

    def log_completion(
        self,
        method: str,
        path: str,
        status_code: int = 200,
        model: str = "",
        cost_usd: float = 0.0,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> None:
        """Log request completion with performance data."""
        duration_ms = (time.perf_counter() - self._start_time) * 1000

        extra = {
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
        }
        if model:
            extra["model"] = model
        if cost_usd > 0:
            extra["cost_usd"] = cost_usd
        if tokens_in > 0:
            extra["tokens_in"] = tokens_in
        if tokens_out > 0:
            extra["tokens_out"] = tokens_out

        logger = logging.getLogger("http")
        logger.info(
            f"{method} {path} {status_code} {duration_ms:.0f}ms",
            extra=extra,
        )
