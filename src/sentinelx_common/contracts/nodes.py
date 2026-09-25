from datetime import datetime
from enum import StrEnum

from pydantic import Field

from sentinelx_common.contracts.base import SentinelXBaseModel


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


class NodeResponse(SentinelXBaseModel):
    """Response data with node details."""

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

    last_seen: datetime | None = Field(default=None, description="Last heartbeat time in UTC")

    created_at: datetime = Field(..., description="Node creation time in UTC")
