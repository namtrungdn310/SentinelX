"""Data models for System API endpoints."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class SystemHealthResponse(BaseModel):
    """Response data for GET /health."""

    status: str = Field(default="ok", description="Current system status")
    service: str = Field(default="sentinelx-controller", description="Service name")
    version: str = Field(default="0.1.0", description="Service version")
    environment: str = Field(default="development", description="Runtime environment")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Current UTC time",
    )


class SystemReadinessResponse(BaseModel):
    """Response data for GET /ready."""

    status: str = Field(description="Current readiness status: 'ready' or 'not_ready'")
    database: str = Field(description="Database connection status: 'connected' or 'disconnected'")
    detail: str | None = Field(default=None, description="Extra information or error message")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Current UTC time",
    )

