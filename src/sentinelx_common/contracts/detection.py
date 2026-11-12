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

    CPU_THRESHOLD = "cpu_threshold_detector"
    MEMORY_EXHAUSTION = "memory_exhaustion_detector"
    DISK_SATURATION = "disk_saturation_detector"


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
        description="IP kẻ tấn công (luôn là None với Resource Anomaly)",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Độ tin cậy từ 0.0 đến 1.0",
    )
    details: ResourceAnomalyDetail = Field(
        ...,
        description="Chi tiết thông số đo đạc",
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
