"""Base data model for all SentinelX contracts.
Uses Pydantic BaseModel with strict settings:
- No extra unknown fields allowed.
- Auto-removes extra spaces around strings.
- Re-checks values if changed.
"""

from pydantic import BaseModel, ConfigDict


class SentinelXBaseModel(BaseModel):
    """Base model for all request and response contracts."""

    model_config = ConfigDict(
        # Do not allow unknown fields
        extra="forbid",
        # Remove whitespace at start and end of strings
        str_strip_whitespace=True,
        # Check values when assigned
        validate_assignment=True,
    )
