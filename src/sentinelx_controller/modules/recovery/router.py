"""API router for recovery and unblock endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
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
from sentinelx_controller.modules.defense.dependencies import get_defense_core
from sentinelx_controller.modules.defense.service import DefenseService
from sentinelx_controller.modules.incidents.router import get_incident_service
from sentinelx_controller.modules.incidents.service import IncidentService
from sentinelx_controller.modules.recovery.repository import RecoveryRepository
from sentinelx_controller.modules.recovery.service import RecoveryService

router = APIRouter(prefix="/recovery", tags=["recovery"])


def get_recovery_service(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
    realtime_hub: Annotated[RealtimeHub, Depends(get_realtime_hub)],
    defense: Annotated[DefenseService, Depends(get_defense_core)],
    incidents: Annotated[IncidentService, Depends(get_incident_service)],
) -> RecoveryService:
    """Dependency providing RecoveryService."""
    recovery_repo = RecoveryRepository(session)
    return RecoveryService(
        recovery_repo=recovery_repo,
        defense_service=defense,
        incident_service=incidents,
        realtime_hub=realtime_hub,
        publisher=CommittedPublisher(background_tasks, realtime_hub),
        safety=request.app.state.settings.safety,
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
    node_id: Annotated[UUID | None, Query(description="Optional node UUID filter")] = None,
) -> list[RecoveryActionResponse]:
    return await service.scan_and_revert_expired_actions(node_id=node_id)
