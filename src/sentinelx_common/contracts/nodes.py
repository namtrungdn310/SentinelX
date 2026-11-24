from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field

from sentinelx_common.contracts.base import SentinelXBaseModel

NodeLBRoleType = Literal["standalone", "lb_backend"]


class NodeStatus(StrEnum):
    """Current status of a managed node."""

    UNENROLLED = "unenrolled"
    ONLINE = "online"
    OFFLINE = "offline"


class NodeRegisterRequest(SentinelXBaseModel):
    """Request data to register a new Linux node."""

    project_id: str = Field(
        ...,
        min_length=36,
        max_length=36,
        description="Project UUID string",
    )

    hostname: str = Field(
        ...,
        min_length=1,
        max_length=36,
        description="Node hostname (e.g. server-01)",
    )

    ip_address: str = Field(
        ...,
        min_length=7,
        max_length=45,
        description="Node IP address (IPv4 or IPv6)",
    )

    os_info: str | None = Field(
        default=None,
        max_length=255,
        description="Operating system description (e.g. Ubuntu 22.04 LTS)",
    )

    lb_role: NodeLBRoleType = Field(
        default="standalone",
        description="Whether this node serves as an upstream backend in the project Load Balancer",
    )
    lb_backend_port: int = Field(
        default=8080,
        ge=1,
        le=65535,
        description="Application HTTP port when lb_role is lb_backend",
    )
    lb_health_path: str | None = Field(
        default=None,
        max_length=255,
        description="Optional HTTP health probe path override for this backend",
    )


class NodeUpdateRequest(SentinelXBaseModel):
    """Partial update request for a registered node."""

    hostname: str | None = Field(default=None, min_length=1, max_length=36)
    os_info: str | None = Field(default=None, max_length=255)
    lb_role: NodeLBRoleType | None = None
    lb_backend_port: int | None = Field(default=None, ge=1, le=65535)
    lb_health_path: str | None = Field(default=None, max_length=255)


class NodeResponse(SentinelXBaseModel):
    """Response data with node details."""

    agent_capabilities: dict[str, Any] = Field(default_factory=dict)

    node_id: str = Field(
        ...,
        min_length=36,
        max_length=36,
        description="Node UUID string",
    )

    project_id: str = Field(
        ...,
        min_length=36,
        max_length=36,
        description="Project UUID string",
    )

    hostname: str = Field(..., description="Node hostname")

    ip_address: str = Field(..., description="Node IP address")

    status: NodeStatus = Field(default=NodeStatus.UNENROLLED, description="Current node status")

    os_info: str | None = Field(default=None, description="Operating system description")

    lb_role: NodeLBRoleType = Field(
        default="standalone",
        description="Load Balancer pool role",
    )
    lb_backend_port: int = Field(
        default=8080,
        description="Application HTTP port for LB backend",
    )
    lb_health_path: str | None = Field(
        default=None,
        description="Optional HTTP health check path override",
    )

    last_seen: datetime | None = Field(default=None, description="Last heartbeat time in UTC")

    created_at: datetime = Field(..., description="Node creation time in UTC")
