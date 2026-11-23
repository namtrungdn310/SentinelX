"""Project contracts for SentinelX.
Data models to create and view projects.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field

from sentinelx_common.contracts.base import SentinelXBaseModel

TelemetryProfileType = Literal["balanced", "high_sensitivity", "resource_saving"]


class ProjectCreateRequest(SentinelXBaseModel):
    """Request data to create a new project."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Project name",
    )

    description: str | None = Field(
        default=None,
        max_length=500,
        description="Optional project description",
    )


class ProjectResponse(SentinelXBaseModel):
    """Response data with project details."""

    project_id: str = Field(
        ...,
        min_length=36,
        max_length=36,
        description="Project UUID string",
    )

    name: str = Field(..., description="Project name")

    description: str | None = Field(default=None, description="Project description")

    created_at: datetime = Field(..., description="Creation time in UTC")


class ProjectSettingsUpdateRequest(SentinelXBaseModel):
    """Request payload to update telemetry preset profile for a project or node."""

    active_profile: TelemetryProfileType = Field(..., description="Preset profile ID")
    updated_by: str = Field(
        default="admin@sentinelx.com",
        max_length=120,
        description="Operator identifier",
    )


class ProjectSettingsResponse(SentinelXBaseModel):
    """Persisted telemetry profile settings returned by Controller."""

    project_id: str = Field(..., min_length=36, max_length=36)
    node_id: str | None = Field(default=None, min_length=36, max_length=36)
    active_profile: TelemetryProfileType = Field(default="balanced")
    updated_at: datetime
    updated_by: str = Field(default="system")
