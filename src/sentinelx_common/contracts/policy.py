"""Defense policy and IP whitelist wire contracts for SentinelX."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from sentinelx_common.contracts.base import SentinelXBaseModel
from sentinelx_common.contracts.detection import DetectionEventContract


class PolicyActionType(StrEnum):
    """Danh mục hành động phòng thủ mở rộng trong SentinelX."""

    # Can thiệp Mạng & Firewall (Stateful & Recovery)
    BLOCK_IP_NFTABLES = "BLOCK_IP_NFTABLES"
    UNBLOCK_IP_NFTABLES = "UNBLOCK_IP_NFTABLES"
    RATE_LIMIT = "RATE_LIMIT"

    # Can thiệp Tài nguyên Host (Instantaneous)
    RESTART_SERVICE = "RESTART_SERVICE"
    KILL_PROCESS = "KILL_PROCESS"
    CLEAR_OS_CACHE = "CLEAR_OS_CACHE"
    CLEANUP_DISK = "CLEANUP_DISK"

    # Can thiệp Điều phối Lưu lượng (Traffic Plane)
    EJECT_NODE = "EJECT_NODE"

    # Chế độ An toàn (Safe Mode)
    ALERT_ONLY = "ALERT_ONLY"


class PolicyEvaluationStatus(StrEnum):
    """Kết quả thẩm định từ PolicyEngine."""

    ACTION_AUTHORIZED = "ACTION_AUTHORIZED"
    DENIED_WHITELIST = "DENIED_WHITELIST"
    DENIED_COOLDOWN = "DENIED_COOLDOWN"
    DENIED_DUPLICATE = "DENIED_DUPLICATE"
    DENIED_DISABLED = "DENIED_DISABLED"
    NO_POLICY_MATCH = "NO_POLICY_MATCH"


class DefensePolicyCreateRequest(SentinelXBaseModel):
    """Yêu cầu tạo mới chính sách phòng thủ."""

    name: str = Field(..., min_length=1, max_length=100, description="Tên chính sách")
    event_type: str = Field(..., min_length=1, max_length=100, description="Loại sự kiện trigger")
    action_type: PolicyActionType = Field(..., description="Hành động phòng thủ kích hoạt")
    target_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Tham số bổ sung (vd: service_name)",
    )
    is_auto_execute: bool = Field(default=True, description="Tự động bắn lệnh xuống agent")
    cooldown_seconds: int = Field(default=300, ge=0, description="Thời gian hạ nhiệt (giây)")
    block_duration_seconds: int = Field(
        default=1800,
        ge=0,
        description="Thời hạn duy trì chặn (giây)",
    )
    enabled: bool = Field(default=True, description="Trạng thái kích hoạt của policy")


class DefensePolicyUpdateRequest(SentinelXBaseModel):
    """Yêu cầu cập nhật chính sách phòng thủ."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    action_type: PolicyActionType | None = None
    target_params: dict[str, Any] | None = None
    is_auto_execute: bool | None = None
    cooldown_seconds: int | None = Field(default=None, ge=0)
    block_duration_seconds: int | None = Field(default=None, ge=0)
    enabled: bool | None = None


class DefensePolicyResponse(SentinelXBaseModel):
    """Chi tiết chính sách phòng thủ."""

    id: str = Field(..., description="UUID của policy")
    project_id: str = Field(..., description="UUID của project")
    name: str
    event_type: str
    action_type: PolicyActionType
    target_params: dict[str, Any]
    is_auto_execute: bool
    cooldown_seconds: int
    block_duration_seconds: int
    enabled: bool


class DefensePolicyListResponse(SentinelXBaseModel):
    """Danh sách chính sách phòng thủ phân trang."""

    total: int = Field(..., ge=0)
    items: list[DefensePolicyResponse]


class IPWhitelistCreateRequest(SentinelXBaseModel):
    """Yêu cầu thêm dải IP an toàn vào Whitelist."""

    ip_or_cidr: str = Field(
        ...,
        min_length=3,
        max_length=45,
        description="Địa chỉ IPv4, IPv6 hoặc CIDR",
    )
    description: str | None = Field(default=None, max_length=255, description="Mô tả mục đích IP")


class IPWhitelistResponse(SentinelXBaseModel):
    """Chi tiết dải IP an toàn."""

    id: str = Field(..., description="UUID của whitelist record")
    project_id: str = Field(..., description="UUID của project")
    ip_or_cidr: str
    description: str | None
    created_at: datetime


class IPWhitelistListResponse(SentinelXBaseModel):
    """Danh sách các dải IP an toàn trong project."""

    total: int = Field(..., ge=0)
    items: list[IPWhitelistResponse]


class PolicyEvaluationRequest(SentinelXBaseModel):
    """Yêu cầu đánh giá chính sách (dùng cho dry-run hoặc kiểm thử)."""

    event: DetectionEventContract


class PolicyEvaluationResult(SentinelXBaseModel):
    """Kết quả đánh giá từ PolicyEngine."""

    authorized: bool = Field(..., description="Có được phép kích hoạt hành động không")
    status: PolicyEvaluationStatus = Field(..., description="Trạng thái phân loại quyết định")
    action_type: PolicyActionType | None = Field(
        default=None,
        description="Hành động được ủy quyền",
    )
    target: str | None = Field(default=None, description="Mục tiêu can thiệp (IP, service, PID)")
    duration_seconds: int = Field(default=0, ge=0, description="Thời hạn hiệu lực nếu có")
    policy_id: str | None = Field(default=None, description="UUID của policy đã match")
    is_auto_execute: bool = Field(
        default=True,
        description="Cho phép tự động thi hành hay cần phê duyệt",
    )
    reason: str = Field(..., description="Giải thích lý do phê duyệt hoặc từ chối")
