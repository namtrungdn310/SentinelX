"""Project contracts for SentinelX.
Data models to create and view projects.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from sentinelx_common.contracts.base import SentinelXBaseModel

TelemetryProfileType = Literal["balanced", "high_sensitivity", "resource_saving"]
LBAlgorithmType = Literal["round_robin", "least_in_flight"]


class ProjectLBConfigContract(SentinelXBaseModel):
    """Per-project optional Load Balancer configuration."""

    enabled: bool = Field(default=False, description="Whether Load Balancer is enabled")
    lb_url: str | None = Field(
        default=None,
        max_length=255,
        description="Base URL of sentinelx_lb management endpoint (e.g. http://192.168.1.100:8080)",
    )
    algorithm: LBAlgorithmType = Field(
        default="round_robin",
        description="Distribution strategy: round_robin or least_in_flight",
    )
    health_path: str = Field(default="/health", min_length=1, max_length=255)
    health_interval_seconds: float = Field(default=3.0, ge=0.5, le=300.0)
    failure_threshold: int = Field(default=3, ge=1, le=20)
    success_threshold: int = Field(default=2, ge=1, le=20)

    @field_validator("lb_url")
    @classmethod
    def validate_lb_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().rstrip("/")
        if not cleaned:
            return None
        if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
            raise ValueError("lb_url must start with http:// or https://")
        return cleaned


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

    load_balancer: ProjectLBConfigContract | None = Field(
        default=None,
        description="Optional per-project Load Balancer configuration",
    )


class ProjectUpdateRequest(SentinelXBaseModel):
    """Request data to update project metadata or LB settings."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    load_balancer: ProjectLBConfigContract | None = None


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

    load_balancer: ProjectLBConfigContract = Field(
        default_factory=ProjectLBConfigContract,
        description="Per-project Load Balancer configuration",
    )

    created_at: datetime = Field(..., description="Creation time in UTC")


class LBAlgorithmUpdateRequest(SentinelXBaseModel):
    """Request payload to hot-switch Load Balancer routing algorithm."""

    algorithm: LBAlgorithmType


class LBBackendStateUpdateRequest(SentinelXBaseModel):
    """Request payload to manually enable or drain/eject a backend."""

    enabled: bool
    force: bool = False


class LBBackendRuntimeResponse(SentinelXBaseModel):
    """Runtime status of a backend inside the Load Balancer pool."""

    name: str
    url: str
    node_id: str | None = None
    weight: int = 1
    health_path: str | None = None
    is_healthy: bool = True
    admin_enabled: bool = True
    health_state: str = "healthy"
    in_flight: int = 0
    total_requests: int = 0
    success_requests: int = 0
    error_requests: int = 0
    consecutive_successes: int = 0
    consecutive_failures: int = 0
    last_health_check_at: str | None = None
    last_health_status_code: int | None = None
    last_health_error: str | None = None
    flapping_detected: bool = False


class ProjectLBStatusResponse(SentinelXBaseModel):
    """Aggregated Load Balancer pool runtime state and Controller sync status."""

    project_id: str = Field(..., min_length=36, max_length=36)
    enabled: bool = False
    lb_url: str | None = None
    algorithm: LBAlgorithmType = "round_robin"
    reachable: bool = False
    sync_status: Literal["disabled", "synced", "unreachable", "error"] = "disabled"
    sync_message: str | None = None
    health_check: dict[str, object] = Field(default_factory=dict)
    total_backends: int = 0
    healthy_backends: int = 0
    routable_backends: int = 0
    admin_disabled_backends: int = 0
    total_in_flight: int = 0
    total_requests: int = 0
    total_success: int = 0
    total_errors: int = 0
    backends: list[LBBackendRuntimeResponse] = Field(default_factory=list)


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
