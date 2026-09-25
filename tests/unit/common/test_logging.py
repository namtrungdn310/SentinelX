"""Tests for logging and correlation ID."""

import json
import logging

from sentinelx_common.observability.logging import (
    JSONFormatter,
    get_correlation_id,
    set_correlation_id,
    setup_logging,
)


def test_correlation_id_context() -> None:
    """Test setting, getting, and resetting correlation ID."""
    assert get_correlation_id() is None

    set_correlation_id("test-corr-123")
    assert get_correlation_id() == "test-corr-123"

    set_correlation_id(None)
    assert get_correlation_id() is None


def test_json_formatter_structure() -> None:
    """Test that JSONFormatter outputs correct JSON fields."""
    formatter = JSONFormatter(service_name="test-service")
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Hello %s",
        args=("world",),
        exc_info=None,
    )
    record.__dict__["custom_field"] = "custom_value"

    set_correlation_id("corr-xyz")
    try:
        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["message"] == "Hello world"
        assert data["level"] == "INFO"
        assert data["logger"] == "test_logger"
        assert data["service"] == "test-service"
        assert data["correlation_id"] == "corr-xyz"
        assert data["extra"]["custom_field"] == "custom_value"
        assert "timestamp" in data
    finally:
        set_correlation_id(None)


def test_setup_logging() -> None:
    """Test setting up logger with debug level."""
    setup_logging(level="DEBUG", json_format=True, service_name="test-sentinelx")
    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG
    assert len(root_logger.handlers) == 1
