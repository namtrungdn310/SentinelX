"""Realtime WebSocket event contracts for SentinelX."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from sentinelx_common.contracts.base import SentinelXBaseModel
from sentinelx_common.contracts.telemetry import MetricSample


class RealtimeEventType(StrEnum):
    """Enumeration of supported realtime WebSocket events."""

    METRIC_UPDATE = "metric_update"
    NODE_STATUS = "node_status"
    PING = "ping"
    PONG = "pong"


class RealtimeMetricPayload(SentinelXBaseModel):
    """Payload data carried when metrics are received and broadcasted."""

    node_id: str = Field(
        ...,
        min_length=36,
        max_length=36,
        description="Node UUID string",
    )
    samples: list[MetricSample] = Field(
        default_factory=list,
        description="List of newly ingested metric samples",
    )
    received_at: datetime = Field(
        ...,
        description="Time when Controller accepted the metrics in UTC",
    )


class RealtimeMessage(SentinelXBaseModel):
    """Standard wire envelope for all WebSocket messages."""

    event: str = Field(
        ...,
        description="Event type name (e.g. metric_update, pong)",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Event payload attributes",
    )
    timestamp: datetime = Field(
        ...,
        description="UTC time when this message was emitted",
    )
