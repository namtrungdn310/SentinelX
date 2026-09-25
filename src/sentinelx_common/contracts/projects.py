"""Project contracts for SentinelX.
Data models to create and view projects.
"""

from datetime import datetime

from pydantic import Field

from sentinelx_common.contracts.base import SentinelXBaseModel


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
