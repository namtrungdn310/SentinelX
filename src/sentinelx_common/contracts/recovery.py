"""Recovery wire contracts and enums for SentinelX."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from sentinelx_common.contracts.base import SentinelXBaseModel


class RecoveryReason(StrEnum):
    """Reason triggering recovery / unblock action."""

    TIMEOUT_EXPIRED = "TIMEOUT_EXPIRED"
    MANUAL_UNBLOCK = "MANUAL_UNBLOCK"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class RecoveryStatus(StrEnum):
    """Lifecycle status of a recovery action."""

    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class RecoveryActionType(StrEnum):
    """Types of recovery actions."""

    UNBLOCK_IP_NFTABLES = "UNBLOCK_IP_NFTABLES"


class RecoveryActionResponse(SentinelXBaseModel):
    """Representation of a persisted recovery action."""

    id: str = Field(..., description="UUID of the recovery action")
    defense_action_id: str = Field(..., description="UUID of the related defense action")
    reason: RecoveryReason = Field(..., description="Reason for recovery")
    status: RecoveryStatus = Field(..., description="Status of recovery action")
    executed_at: datetime = Field(..., description="Execution timestamp in UTC")


class RecoveryActionListResponse(SentinelXBaseModel):
    """Paginated list of recovery actions."""

    total: int = Field(..., ge=0, description="Total count of matching recovery actions")
    items: list[RecoveryActionResponse] = Field(..., description="List of recovery actions")


class ManualRevertRequest(SentinelXBaseModel):
    """Request payload to manually revert / unblock a defense action."""

    reason: RecoveryReason = Field(
        default=RecoveryReason.MANUAL_UNBLOCK,
        description="Reason for manually reverting the defense action",
    )
