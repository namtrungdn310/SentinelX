"""Agent contracts for SentinelX.
Data models for Agent enrollment and heartbeat.
"""

from datetime import datetime

from pydantic import Field

from sentinelx_common.contracts.base import SentinelXBaseModel


class AgentEnrollRequest(SentinelXBaseModel):
    """Request data to enroll a new Agent with the Controller."""

    node_id: str = Field(
        ...,
        min_length=36,
        max_length=36,
        description="Node UUID string",
    )

    enrollment_token: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Secret token to authorize enrollment",
    )
    agent_version: str = Field(
        default="0.1.0",
        max_length=32,
        description="Agent software version",
    )
    hostname: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Hostname of the Linux machine",
    )
    os_info: str | None = Field(
        default=None,
        max_length=255,
        description="Operating system description",
    )


class AgentEnrollResponse(SentinelXBaseModel):
    """Response data returned after successful enrollment."""

    agent_id: str = Field(
        ...,
        min_length=36,
        max_length=36,
        description="Agent UUID string",
    )
    node_id: str = Field(
        ...,
        min_length=36,
        max_length=36,
        description="Node UUID string",
    )
    status: str = Field(
        default="enrolled",
        description="Enrollment status (e.g. enrolled)",
    )
    heartbeat_interval_seconds: int = Field(
        default=10,
        ge=1,
        le=3600,
        description="How often the agent should send hearbeats in seconds",
    )
    enrolled_at: datetime = Field(
        ...,
        description="Enrollment time in UTC",
    )


class HeartbeatRequest(SentinelXBaseModel):
    """Heartbeat message sent by Agent to show it is alive."""

    node_id: str = Field(
        ...,
        min_length=36,
        max_length=36,
        description="Node UUID string",
    )

    agent_id: str = Field(
        ...,
        min_length=36,
        max_length=36,
        description="Agent UUID string",
    )
    sequence: int = Field(
        ...,
        ge=1,
        description="Message counter starting from 1",
    )
    sent_at: datetime = Field(
        ...,
        description="Time when Agent sent the heartbeat in UTC",
    )


class HeartbeatResponse(SentinelXBaseModel):
    """Response from Controller confirming heartbeat was received."""

    status: str = Field(
        default="ok",
        description="Status response (e.g. ok)",
    )
    received_at: datetime = Field(
        ...,
        description="Time when Controller received the heartbeat in UTC",
    )

    next_interval_seconds: int = Field(
        default=10,
        ge=1,
        le=3600,
        description="Next heartbeat interval in seconds",
    )
