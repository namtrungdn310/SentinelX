"""Incident wire contracts and enums for SentinelX."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from sentinelx_common.contracts.base import SentinelXBaseModel
from sentinelx_common.contracts.detection import DetectionEventResponse, DetectionSeverity


class IncidentStatus(StrEnum):
    """Trạng thái vòng đời của một vụ việc an ninh."""

    DETECTED = "DETECTED"
    MITIGATING = "MITIGATING"
    RESOLVED = "RESOLVED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class IncidentResponse(SentinelXBaseModel):
    """Thông tin phản hồi của một sự cố an ninh."""

    id: str = Field(..., description="UUID của incident")
    project_id: str = Field(..., description="UUID của project liên quan")
    title: str = Field(..., description="Tiêu đề vụ việc")
    status: IncidentStatus = Field(..., description="Trạng thái hiện tại của incident")
    severity: DetectionSeverity = Field(..., description="Mức độ nghiêm trọng tổng hợp")
    started_at: datetime = Field(..., description="Thời điểm bắt đầu ghi nhận sự cố")
    resolved_at: datetime | None = Field(default=None, description="Thời điểm kết thúc sự cố")
    summary: str | None = Field(default=None, description="Tóm tắt tiến trình và hành động")
    event_count: int = Field(default=0, description="Tổng số detection events thuộc incident này")


class IncidentDetailResponse(IncidentResponse):
    """Chi tiết sự cố kèm danh sách các detection events cấu thành."""

    events: list[DetectionEventResponse] = Field(
        default_factory=list,
        description="Danh sách sự kiện bất thường liên quan",
    )


class IncidentUpdateRequest(SentinelXBaseModel):
    """Yêu cầu cập nhật trạng thái hoặc tóm tắt vụ việc."""

    status: IncidentStatus | None = Field(default=None, description="Trạng thái mới cần chuyển")
    summary: str | None = Field(default=None, description="Tóm tắt cập nhật")


class IncidentListResponse(SentinelXBaseModel):
    """Danh sách các vụ việc phân trang."""

    total: int = Field(..., ge=0, description="Tổng số incident khớp bộ lọc")
    items: list[IncidentResponse] = Field(..., description="Danh sách incident trên trang hiện tại")
