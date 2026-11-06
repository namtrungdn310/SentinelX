"""M2 wire contracts: bounded network metadata, never packet payloads."""

from datetime import UTC, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, IPvAnyAddress, field_validator, model_validator

from sentinelx_common.contracts.base import SentinelXBaseModel

Port = Annotated[int, Field(ge=0, le=65535)]


class NetworkFeature(SentinelXBaseModel):
    """Directional IP pair/protocol summary within one sliding window."""

    source_ip: IPvAnyAddress
    destination_ip: IPvAnyAddress
    protocol: Literal["tcp", "udp", "icmp", "other"]
    packet_count: int = Field(ge=1)
    byte_count: int = Field(ge=0, description="Observed IP bytes, not application payload bytes")
    syn_count: int = Field(default=0, ge=0)
    ack_count: int = Field(default=0, ge=0)
    rst_count: int = Field(default=0, ge=0)
    fin_count: int = Field(default=0, ge=0)
    destination_ports: list[Port] = Field(default_factory=list, max_length=256)
    ports_truncated: bool = False

    @model_validator(mode="after")
    def validate_counters(self) -> Self:
        flags = (self.syn_count, self.ack_count, self.rst_count, self.fin_count)
        if any(count > self.packet_count for count in flags):
            raise ValueError("TCP flag counts cannot exceed packet_count")
        if self.protocol != "tcp" and any(flags):
            raise ValueError("TCP flags require protocol=tcp")
        if self.protocol not in {"tcp", "udp"} and self.destination_ports:
            raise ValueError("Transport ports require TCP or UDP")
        if self.destination_ports != sorted(set(self.destination_ports)):
            raise ValueError("destination_ports must be sorted and unique")
        return self


class NetworkWindow(SentinelXBaseModel):
    """One completed observation window; empty features means capture was running."""

    window_id: UUID
    window_start: AwareDatetime
    window_end: AwareDatetime
    interface: str = Field(min_length=1, max_length=64)
    features: list[NetworkFeature] = Field(default_factory=list, max_length=1024)
    omitted_packets: int = Field(default=0, ge=0, le=2**63 - 1)
    skipped_windows: int = Field(default=0, ge=0)

    @field_validator("window_start", "window_end")
    @classmethod
    def utc_times(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        duration = (self.window_end - self.window_start).total_seconds()
        if not 0 < duration <= 300:
            raise ValueError("Window duration must be positive and at most 300 seconds")
        keys = [(str(f.source_ip), str(f.destination_ip), f.protocol) for f in self.features]
        if len(set(keys)) != len(keys):
            raise ValueError("Duplicate feature groups in a window")
        return self


class NetworkBatchRequest(SentinelXBaseModel):
    node_id: UUID
    agent_id: UUID
    sequence: int = Field(ge=1)
    sent_at: AwareDatetime
    windows: list[NetworkWindow] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def unique_windows(self) -> Self:
        if len({window.window_id for window in self.windows}) != len(self.windows):
            raise ValueError("Duplicate window IDs in one batch")
        return self


class NetworkBatchResponse(SentinelXBaseModel):
    status: str = "ok"
    processed_count: int = Field(ge=0)
    received_at: datetime


class NetworkQueryResponse(SentinelXBaseModel):
    node_id: UUID
    count: int = Field(ge=0)
    windows: list[NetworkWindow] = Field(default_factory=list)
