"""Structured logging utilities with JSON formatting and correlation ID support."""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# ContextVar storing the current request/pipeline correlation ID
_CORRELATION_ID_CTX: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    """Retrieve the current correlation ID from context."""
    return _CORRELATION_ID_CTX.get()


def set_correlation_id(correlation_id: str | None) -> None:
    """Set or clear the correlation ID in context."""
    _CORRELATION_ID_CTX.set(correlation_id)


class JSONFormatter(logging.Formatter):
    """Formatter that outputs structured JSON log entries."""

    def __init__(self, service_name: str = "sentinelx") -> None:
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as a structured JSON object."""
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
        }

        correlation_id = get_correlation_id()
        if correlation_id:
            log_entry["correlation_id"] = correlation_id

        # Include custom extra fields if attached to the record
        standard_attrs = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
        }
        extra_fields = {
            k: v
            for k, v in record.__dict__.items()
            if k not in standard_attrs and not k.startswith("_")
        }
        if extra_fields:
            log_entry["extra"] = extra_fields

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(
    level: str = "INFO",
    json_format: bool = True,
    service_name: str = "sentinelx",
) -> None:
    """Configure the root logger with either structured JSON or standard formatting.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_format: If True, uses JSONFormatter; otherwise standard stream formatting.
        service_name: Name of the service producing logs.
    """
    root_logger = logging.getLogger()
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)

    if json_format:
        handler.setFormatter(JSONFormatter(service_name=service_name))
    else:
        standard_format = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
        handler.setFormatter(logging.Formatter(standard_format))

    root_logger.addHandler(handler)
