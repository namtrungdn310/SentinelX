"""Schemas for System module endpoints."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class SystemHealthResponse(BaseModel):
    """Health check response payload."""

    status: str = Field(default="ok", description="Current system operational status")
    service: str = Field(default="sentinelx-controller", description="Service name")
    version: str = Field(default="0.1.0", description="Service version")
    environment: str = Field(default="development", description="Runtime environment")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp of health observation (UTC)",
    )
