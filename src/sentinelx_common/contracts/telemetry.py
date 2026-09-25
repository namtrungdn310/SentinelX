"""Telemetry and metric contracts for SentinelX.
Data models for CPU, RAM, Disk, and Network metrics sent in batches.
"""

from datetime import datetime

from pydantic import Field

from sentinelx_common.contracts.base import SentinelXBaseModel


class MetricSample(SentinelXBaseModel):
    """Single measurement of machine metrics at one moment."""

    observed_at: datetime = Field(
        ...,
        description="Time when metrics were collected in UTC",
    )
    cpu_percent: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="CPU usage percentage from 0.0 to 100.0",
    )

    memory_percent: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="RAM usage percentage from 0.0 to 100.0",
    )
    disk_percent: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Optional disk usage percentage from 0.0 to 100.0",
    )

    network_tx_bytes: int | None = Field(
        default=None,
        ge=0,
        description="Bytes sent since last check",
    )

    network_rx_bytes: int | None = Field(
        default=None,
        ge=0,
        description="Bytes received since last check",
    )


class MetricBatchRequest(SentinelXBaseModel):
    """Batch of metric samples sent from Agent to Controller."""

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
        description="Message counter strating from 1",
    )

    sent_at: datetime = Field(
        ...,
        description="Time when batch was sent in UTC",
    )
    samples: list[MetricSample] = Field(
        ...,
        min_length=1,
        description="List of metric samples (must have at least 1)",
    )


class MetricBatchResponse(SentinelXBaseModel):
    """Response from Controller confirming metrics were saved."""

    status: str = Field(
        default="ok",
        description="Status response (e.g. ok)",
    )
    processed_count: int = Field(
        ...,
        ge=0,
        description="Number of metric samples saved",
    )
    received_at: datetime = Field(
        ...,
        description="Time when Controller received the batch in UTC",
    )
