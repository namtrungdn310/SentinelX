"""Detection wire contracts and enums for SentinelX."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from sentinelx_common.contracts.base import SentinelXBaseModel


class DetectionSeverity(StrEnum):
    """Mức độ nghiêm trọng của sự kiện bất thường."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DetectorType(StrEnum):
    """Định danh các bộ detector phát hiện bất thường."""

    # Resource Detectors (M3)
    CPU_THRESHOLD = "cpu_threshold_detector"
    MEMORY_EXHAUSTION = "memory_exhaustion_detector"
    DISK_SATURATION = "disk_saturation_detector"

    # Network Detectors (M4)
    SYN_FLOOD = "syn_flood_detector"
    PORT_SCAN = "port_scan_detector"
    TRAFFIC_SPIKE = "traffic_spike_detector"


class ResourceAnomalyDetail(SentinelXBaseModel):
    """Cấu trúc dữ liệu chi tiết cho sự kiện bất thường tài nguyên."""

    metric_name: str = Field(
        ...,
        description="Tên metric bị vượt ngưỡng: cpu_percent, memory_percent, disk_percent",
    )
    current_value: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Giá trị đo được hiện tại",
    )
    threshold_value: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Ngưỡng kích hoạt cảnh báo",
    )
    window_duration_seconds: int = Field(
        ...,
        ge=0,
        description="Khoảng thời gian (giây) duy trì trạng thái vượt ngưỡng",
    )
    consecutive_samples: int = Field(
        ...,
        ge=1,
        description="Số mẫu đo liên tiếp vi phạm ngưỡng",
    )
    extra_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Thông tin ngữ cảnh bổ sung",
    )


class NetworkAnomalyDetail(SentinelXBaseModel):
    """Cấu trúc dữ liệu chi tiết cho sự kiện bất thường mạng (Milestone M4)."""

    attack_type: str = Field(
        ...,
        description="Loại tấn công mạng: SYN_FLOOD, PORT_SCAN, TRAFFIC_SPIKE",
    )
    source_ip: str = Field(
        ...,
        description="Địa chỉ IP nguồn phát sinh tấn công (attacker_ip)",
    )
    destination_ip: str = Field(
        ...,
        description="Địa chỉ IP đích của server",
    )
    protocol: str = Field(
        ...,
        description="Giao thức mạng: tcp, udp, icmp, other",
    )
    packet_count: int = Field(
        ...,
        ge=0,
        description="Tổng số gói tin quan sát được trong cửa sổ",
    )
    byte_count: int = Field(
        default=0,
        ge=0,
        description="Tổng số bytes quan sát được trong cửa sổ",
    )
    syn_count: int = Field(
        default=0,
        ge=0,
        description="Số lượng cờ SYN",
    )
    ack_count: int = Field(
        default=0,
        ge=0,
        description="Số lượng cờ ACK",
    )
    targeted_ports: list[int] = Field(
        default_factory=list,
        description="Danh sách cổng bị thăm dò hoặc tấn công",
    )
    metric_ratio: float | None = Field(
        default=None,
        description="Tỷ lệ kích hoạt bất thường (ví dụ: syn/ack ratio)",
    )
    extra_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Thông tin ngữ cảnh bổ sung",
    )


class DetectionEventContract(SentinelXBaseModel):
    """Contract nội bộ đại diện cho một sự kiện bất thường do Detector bắn ra."""

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="UUID của detection event",
    )
    incident_id: str | None = Field(
        default=None,
        description="UUID của incident liên kết nếu có",
    )
    node_id: str = Field(
        ...,
        min_length=36,
        max_length=36,
        description="Node UUID string",
    )
    detector_name: str = Field(
        ...,
        description="Tên của bộ detector phát hiện sự kiện",
    )
    severity: DetectionSeverity = Field(
        ...,
        description="Mức độ nghiêm trọng của sự kiện",
    )
    attacker_ip: str | None = Field(
        default=None,
        description="IP kẻ tấn công (None với Resource Anomaly, có giá trị với Network Anomaly)",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Độ tin cậy từ 0.0 đến 1.0",
    )
    details: ResourceAnomalyDetail | NetworkAnomalyDetail = Field(
        ...,
        description="Chi tiết thông số đo đạc bất thường",
    )
    detected_at: datetime = Field(
        ...,
        description="Thời điểm phát hiện sự kiện theo UTC",
    )


class DetectionEventResponse(SentinelXBaseModel):
    """Response trả về thông tin chi tiết một sự kiện qua REST API."""

    id: str
    incident_id: str | None = None
    node_id: str
    detector_name: str
    severity: DetectionSeverity
    attacker_ip: str | None = None
    confidence_score: float
    details: dict[str, Any]
    detected_at: datetime


class DetectionEventListResponse(SentinelXBaseModel):
    """Response danh sách sự kiện có phân trang."""

    total: int
    items: list[DetectionEventResponse]
