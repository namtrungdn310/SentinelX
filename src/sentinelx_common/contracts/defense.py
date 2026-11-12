"""Defense action and command pipeline wire contracts for SentinelX."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from sentinelx_common.contracts.base import SentinelXBaseModel
from sentinelx_common.contracts.policy import PolicyActionType


class DefenseActionStatus(StrEnum):
    """Lifecycle status of a defense action command."""

    PENDING = "PENDING"
    SENT = "SENT"
    APPLIED = "APPLIED"
    FAILED = "FAILED"
    REVERTED = "REVERTED"


class AgentCommandContract(SentinelXBaseModel):
    """Command payload sent down to an agent."""

    id: str = Field(..., description="UUID of the defense action")
    action_type: str = Field(..., description="Type of action (e.g. BLOCK_IP_NFTABLES)")
    target_ip: str | None = Field(default=None, description="Target IP if applicable")
    command_payload: dict[str, Any] = Field(default_factory=dict, description="Command parameters")
    created_at: datetime = Field(..., description="Command creation timestamp in UTC")


class CommandAckRequest(SentinelXBaseModel):
    """Request sent by agent to report command execution outcome."""

    action_id: str = Field(..., description="UUID of the defense action")
    status: DefenseActionStatus = Field(..., description="Execution status: APPLIED or FAILED")
    error_message: str | None = Field(default=None, description="Error message if execution failed")
    execution_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Execution details from the executor",
    )


class CommandAckResponse(SentinelXBaseModel):
    """Response returned to agent after processing acknowledgment."""

    status: str = Field(default="ok", description="Status confirmation")
    action_id: str = Field(..., description="UUID of the acknowledged action")
    acknowledged_at: datetime = Field(..., description="Timestamp of acknowledgment in UTC")


class DefenseActionResponse(SentinelXBaseModel):
    """Representation of a persisted defense action."""

    id: str = Field(..., description="UUID of the defense action")
    incident_id: str | None = Field(default=None, description="UUID of associated incident")
    policy_id: str | None = Field(default=None, description="UUID of triggering defense policy")
    node_id: str = Field(..., description="UUID of the target node")
    action_type: str = Field(..., description="Type of action")
    target_ip: str | None = Field(default=None, description="Target IP if applicable")
    command_payload: dict[str, Any] = Field(..., description="Action parameters and context")
    status: DefenseActionStatus = Field(..., description="Current status")
    agent_ack_at: datetime | None = Field(default=None, description="When agent acknowledged")
    error_message: str | None = Field(default=None, description="Error details if failed")
    created_at: datetime = Field(..., description="Creation timestamp in UTC")


class DefenseActionListResponse(SentinelXBaseModel):
    """Paginated list of defense actions."""

    total: int = Field(..., ge=0, description="Total count of matching actions")
    items: list[DefenseActionResponse] = Field(..., description="List of defense actions")


class ManualDefenseActionCreateRequest(SentinelXBaseModel):
    """Request from operator/dashboard to manually trigger a defense action."""

    node_id: str = Field(..., description="UUID of the target node")
    action_type: PolicyActionType = Field(..., description="Action to execute")
    target_ip: str | None = Field(default=None, description="Target IP if applicable")
    command_payload: dict[str, Any] = Field(default_factory=dict, description="Custom parameters")
    incident_id: str | None = Field(default=None, description="Optional incident correlation ID")
