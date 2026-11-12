"""API router for recovery and unblock endpoints."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_common.contracts.recovery import (
    ManualRevertRequest,
    RecoveryActionListResponse,
    RecoveryActionResponse,
)
from sentinelx_controller.infrastructure.database.session import get_db_session
from sentinelx_controller.infrastructure.realtime import get_realtime_hub
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub
from sentinelx_controller.infrastructure.realtime.publisher import CommittedPublisher
from sentinelx_controller.modules.defense.repository import DefenseRepository
from sentinelx_controller.modules.incidents.repository import IncidentRepository
from sentinelx_controller.modules.recovery.repository import RecoveryRepository
from sentinelx_controller.modules.recovery.service import RecoveryService

router = APIRouter(prefix="/recovery", tags=["recovery"])


def get_recovery_service(
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
    realtime_hub: Annotated[RealtimeHub, Depends(get_realtime_hub)],
) -> RecoveryService:
    """Dependency providing RecoveryService."""
    recovery_repo = RecoveryRepository(session)
    defense_repo = DefenseRepository(session)
    incident_repo = IncidentRepository(session)
    return RecoveryService(
        recovery_repo=recovery_repo,
        defense_repo=defense_repo,
        incident_repo=incident_repo,
        realtime_hub=realtime_hub,
        publisher=CommittedPublisher(background_tasks, realtime_hub),
    )


@router.get(
    "/actions",
    response_model=RecoveryActionListResponse,
    summary="List recovery actions with optional status filter",
)
async def list_recovery_actions(
    service: Annotated[RecoveryService, Depends(get_recovery_service)],
    action_status: str | None = Query(default=None, alias="status", description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> RecoveryActionListResponse:
    return await service.list_recoveries(
        status_filter=action_status,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/actions/{recovery_id}",
    response_model=RecoveryActionResponse,
    summary="Get single recovery action by ID",
)
async def get_recovery_action(
    recovery_id: str,
    service: Annotated[RecoveryService, Depends(get_recovery_service)],
) -> RecoveryActionResponse:
    return await service.get_recovery(recovery_id)


@router.post(
    "/actions/{action_id}/revert",
    response_model=RecoveryActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Manually trigger unblock / recovery for a defense action",
)
async def revert_defense_action(
    action_id: str,
    service: Annotated[RecoveryService, Depends(get_recovery_service)],
    request: ManualRevertRequest | None = None,
) -> RecoveryActionResponse:
    req = request or ManualRevertRequest()
    return await service.revert_defense_action(
        defense_action_id_str=action_id,
        reason=req.reason,
    )


@router.post(
    "/scan-expired",
    response_model=list[RecoveryActionResponse],
    summary="Scan and trigger unblock for expired defense actions",
)
async def scan_expired_defense_actions(
    service: Annotated[RecoveryService, Depends(get_recovery_service)],
    node_id: str | None = Query(default=None, description="Optional node UUID filter"),
) -> list[RecoveryActionResponse]:
    import uuid

    n_uuid = uuid.UUID(node_id) if node_id else None
    return await service.scan_and_revert_expired_actions(node_id=n_uuid)
