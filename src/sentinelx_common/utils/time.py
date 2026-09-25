"""Date and time helper functions.

All services must use UTC time with timezone info.
"""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Get the current time in UTC."""
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    """Make sure datetime has UTC timezone.

    If naive (no timezone), set it to UTC.
    If it has another timezone, convert it to UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_iso8601(dt: datetime) -> str:
    """Convert datetime to standard string with 'Z'.

    Example: '2026-08-28T02:30:00Z'
    """
    utc_dt = ensure_utc(dt)
    return utc_dt.isoformat().replace("+00:00", "Z")


def from_iso8601(val: str) -> datetime:
    """Convert ISO time string to UTC datetime.

    Accepts strings ending with 'Z' or '+00:00'.
    Raises ValueError if the string format is wrong.
    """
    normalized = val.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    dt = datetime.fromisoformat(normalized)
    return ensure_utc(dt)
