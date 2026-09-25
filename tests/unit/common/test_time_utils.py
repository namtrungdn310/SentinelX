"""Tests for time helper functions."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from sentinelx_common.utils.time import (
    ensure_utc,
    from_iso8601,
    to_iso8601,
    utcnow,
)


def test_utcnow_is_timezone_aware() -> None:
    """Test that utcnow returns an aware UTC datetime."""
    now = utcnow()
    assert now.tzinfo is not None
    assert now.tzinfo == UTC


def test_ensure_utc_naive_and_aware() -> None:
    """Test that naive datetime is given UTC, and aware is converted."""
    # Test naive datetime
    naive = datetime(2026, 1, 1, 12, 0, 0)
    aware = ensure_utc(naive)
    assert aware.tzinfo == UTC
    assert aware.hour == 12

    # Test datetime with other timezone (GMT+7)
    tz_plus_7 = timezone(timedelta(hours=7))
    dt_vn = datetime(2026, 1, 1, 19, 0, 0, tzinfo=tz_plus_7)
    converted = ensure_utc(dt_vn)
    assert converted.tzinfo == UTC
    # 19:00 in GMT+7 is 12:00 in UTC
    assert converted.hour == 12


def test_to_iso8601() -> None:
    """Test converting datetime to ISO 8601 string with Z."""
    dt = datetime(2026, 8, 28, 2, 30, 0, tzinfo=UTC)
    iso_str = to_iso8601(dt)
    assert iso_str == "2026-08-28T02:30:00Z"


def test_from_iso8601_valid() -> None:
    """Test parsing valid ISO strings ending with Z or +00:00."""
    dt1 = from_iso8601("2026-08-28T02:30:00Z")
    assert dt1.tzinfo == UTC
    assert dt1.year == 2026
    assert dt1.hour == 2

    dt2 = from_iso8601("2026-08-28T02:30:00+00:00")
    assert dt2 == dt1


def test_from_iso8601_invalid() -> None:
    """Test that invalid string raises ValueError."""
    with pytest.raises(ValueError):
        from_iso8601("not-a-valid-timestamp")
