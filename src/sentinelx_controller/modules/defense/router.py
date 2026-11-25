"""API router for defense module endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from sentinelx_common.contracts.defense import (
    CommandAckRequest,
    CommandAckResponse,
    DefenseActionListResponse,
    DefenseActionResponse,
    ManualDefenseActionCreateRequest,
)
from sentinelx_controller.modules.defense.dependencies import get_defense_core
from sentinelx_controller.modules.defense.service import DefenseService
from sentinelx_controller.modules.recovery.router import get_recovery_service
from sentinelx_controller.modules.recovery.service import RecoveryService

router = APIRouter(prefix="/defense", tags=["defense"])


def get_defense_service(
    core: Annotated[DefenseService, Depends(get_defense_core)],
    recovery: Annotated[RecoveryService, Depends(get_recovery_service)],
) -> DefenseService:
    """Dependency providing DefenseService."""
    core.attach_recovery_handler(recovery.handle_unblock_ack)
    return core


@router.get(
    "/actions",
    response_model=DefenseActionListResponse,
    summary="List defense actions with optional filtering",
)
async def list_defense_actions(
    service: Annotated[DefenseService, Depends(get_defense_service)],
    project_id: str | None = Query(default=None, description="Filter by project UUID"),
    node_id: str | None = Query(default=None, description="Filter by node UUID"),
    incident_id: str | None = Query(default=None, description="Filter by incident UUID"),
    action_status: str | None = Query(default=None, alias="status", description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> DefenseActionListResponse:
    return await service.list_actions(
        node_id_str=node_id,
        project_id_str=project_id,
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


@router.post("/actions/{action_id}/cancel", response_model=DefenseActionResponse)
async def cancel_pending_action(
    action_id: UUID,
    service: Annotated[DefenseService, Depends(get_defense_service)],
) -> DefenseActionResponse:
    return await service.cancel_pending(action_id)
