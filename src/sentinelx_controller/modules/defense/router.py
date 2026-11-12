"""API router for defense module endpoints."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_common.contracts.defense import (
    CommandAckRequest,
    CommandAckResponse,
    DefenseActionListResponse,
    DefenseActionResponse,
    ManualDefenseActionCreateRequest,
)
from sentinelx_controller.infrastructure.database.session import get_db_session
from sentinelx_controller.infrastructure.realtime import get_realtime_hub
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub
from sentinelx_controller.infrastructure.realtime.publisher import CommittedPublisher
from sentinelx_controller.modules.defense.repository import DefenseRepository
from sentinelx_controller.modules.defense.service import DefenseService
from sentinelx_controller.modules.incidents.repository import IncidentRepository
from sentinelx_controller.modules.recovery.repository import RecoveryRepository
from sentinelx_controller.modules.recovery.service import RecoveryService

router = APIRouter(prefix="/defense", tags=["defense"])


def get_defense_service(
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
    realtime_hub: Annotated[RealtimeHub, Depends(get_realtime_hub)],
) -> DefenseService:
    """Dependency providing DefenseService."""
    defense_repo = DefenseRepository(session)
    incident_repo = IncidentRepository(session)
    recovery_repo = RecoveryRepository(session)
    publisher = CommittedPublisher(background_tasks, realtime_hub)
    recovery_service = RecoveryService(
        recovery_repo=recovery_repo,
        defense_repo=defense_repo,
        incident_repo=incident_repo,
        realtime_hub=realtime_hub,
        publisher=publisher,
    )
    return DefenseService(
        defense_repo=defense_repo,
        realtime_hub=realtime_hub,
        publisher=publisher,
        incident_repo=incident_repo,
        recovery_ack_handler=recovery_service.handle_unblock_ack,
    )


@router.get(
    "/actions",
    response_model=DefenseActionListResponse,
    summary="List defense actions with optional filtering",
)
async def list_defense_actions(
    service: Annotated[DefenseService, Depends(get_defense_service)],
    node_id: str | None = Query(default=None, description="Filter by node UUID"),
    incident_id: str | None = Query(default=None, description="Filter by incident UUID"),
    action_status: str | None = Query(default=None, alias="status", description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> DefenseActionListResponse:
    return await service.list_actions(
        node_id_str=node_id,
        incident_id_str=incident_id,
        status_filter=action_status,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/actions/{action_id}",
    response_model=DefenseActionResponse,
    summary="Get single defense action by ID",
)
async def get_defense_action(
    action_id: str,
    service: Annotated[DefenseService, Depends(get_defense_service)],
) -> DefenseActionResponse:
    return await service.get_action(action_id)


@router.post(
    "/actions",
    response_model=DefenseActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a manual defense action (Operator override)",
)
async def create_manual_defense_action(
    request: ManualDefenseActionCreateRequest,
    service: Annotated[DefenseService, Depends(get_defense_service)],
) -> DefenseActionResponse:
    return await service.create_manual_action(request)


@router.post(
    "/actions/{action_id}/ack",
    response_model=CommandAckResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit agent command execution acknowledgment",
)
async def acknowledge_defense_action(
    action_id: str,
    request: CommandAckRequest,
    service: Annotated[DefenseService, Depends(get_defense_service)],
) -> CommandAckResponse:
    return await service.record_ack(action_id, request)
