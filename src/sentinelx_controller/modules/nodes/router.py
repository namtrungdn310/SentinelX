"""API router for node endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from sentinelx_common.contracts.agents import (
    AgentEnrollRequest,
    AgentEnrollResponse,
    EnrollmentTokenCreateRequest,
    EnrollmentTokenResponse,
    HeartbeatRequest,
    HeartbeatResponse,
)
from sentinelx_common.contracts.nodes import (
    NodeRegisterRequest,
    NodeResponse,
    NodeUpdateRequest,
)
from sentinelx_common.contracts.projects import (
    ProjectSettingsResponse,
    ProjectSettingsUpdateRequest,
)
from sentinelx_controller.modules.defense.router import get_defense_service
from sentinelx_controller.modules.defense.service import DefenseService
from sentinelx_controller.modules.nodes.dependencies import get_node_service
from sentinelx_controller.modules.nodes.service import NodeService
from sentinelx_controller.modules.projects.lb_coordinator import ProjectLBCoordinator
from sentinelx_controller.modules.projects.router import get_project_service
from sentinelx_controller.modules.projects.service import ProjectService
from sentinelx_controller.modules.recovery.router import get_recovery_service
from sentinelx_controller.modules.recovery.service import RecoveryService

router = APIRouter(prefix="/nodes", tags=["nodes"])
settings_router = APIRouter(tags=["settings"])


@router.post(
    "",
    response_model=NodeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new node into a project",
)
async def register_node(
    raw_request: Request,
    request: NodeRegisterRequest,
    service: Annotated[NodeService, Depends(get_node_service)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> NodeResponse:
    created = await service.register_node(request)
    if created.lb_role == "lb_backend":
        coordinator = ProjectLBCoordinator(
            project_service=project_service,
            node_service=service,
            lb_admin_token=raw_request.app.state.settings.lb_admin_token,
            default_lb_url=raw_request.app.state.settings.default_lb_url,
        )
        await coordinator.sync_project_lb(created.project_id)
    return created


@router.patch(
    "/{node_id}",
    response_model=NodeResponse,
    summary="Update node metadata or Load Balancer backend settings",
)
async def update_node(
    node_id: str,
    raw_request: Request,
    request: NodeUpdateRequest,
    service: Annotated[NodeService, Depends(get_node_service)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> NodeResponse:
    updated = await service.update_node(node_id, request)
    coordinator = ProjectLBCoordinator(
        project_service=project_service,
        node_service=service,
        lb_admin_token=raw_request.app.state.settings.lb_admin_token,
        default_lb_url=raw_request.app.state.settings.default_lb_url,
    )
    await coordinator.sync_project_lb(updated.project_id)
    return updated


@router.post(
    "/enroll",
    response_model=AgentEnrollResponse,
    status_code=status.HTTP_200_OK,
    summary="Enroll an Agent using an enrollment token",
)
async def enroll_agent(
    request: AgentEnrollRequest,
    service: Annotated[NodeService, Depends(get_node_service)],
) -> AgentEnrollResponse:
    return await service.enroll_agent(request)


@router.post(
    "/heartbeat",
    response_model=HeartbeatResponse,
    status_code=status.HTTP_200_OK,
    summary="Process agent heartbeat and update node liveness",
)
async def process_heartbeat(
    request: HeartbeatRequest,
    service: Annotated[NodeService, Depends(get_node_service)],
    defense_service: Annotated[DefenseService, Depends(get_defense_service)],
    recovery_service: Annotated[RecoveryService, Depends(get_recovery_service)],
) -> HeartbeatResponse:
    # Authenticate before scanning recovery state or claiming commands.
    response = await service.process_heartbeat(request)
    try:
        node_uuid = uuid.UUID(request.node_id)
        await recovery_service.scan_and_revert_expired_actions(node_uuid)
        commands = (
            await defense_service.get_pending_commands_for_node(
                node_uuid, request.supported_actions
            )
            if request.command_protocol_version == 2
            else []
        )
    except ValueError:
        commands = []
    return response.model_copy(update={"commands": commands})


@router.get(
    "",
    response_model=list[NodeResponse],
    summary="List nodes (optional filter by project_id)",
)
async def list_nodes(
    service: Annotated[NodeService, Depends(get_node_service)],
    project_id: Annotated[str | None, Query(description="Filter nodes by project UUID")] = None,
) -> list[NodeResponse]:
    return await service.list_nodes(project_id_str=project_id)


@router.get(
    "/{node_id}",
    response_model=NodeResponse,
    summary="Get node details by ID",
)
async def get_node(
    node_id: str,
    service: Annotated[NodeService, Depends(get_node_service)],
) -> NodeResponse:
    return await service.get_node(node_id)


@router.post(
    "/{node_id}/enrollment-tokens",
    response_model=EnrollmentTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an enrollment token for a node",
)
async def create_enrollment_token(
    node_id: str,
    request: EnrollmentTokenCreateRequest,
    service: Annotated[NodeService, Depends(get_node_service)],
) -> EnrollmentTokenResponse:
    return await service.create_enrollment_token(node_id, request)


@router.get(
    "/{node_id}/enrollment-tokens",
    response_model=list[EnrollmentTokenResponse],
    summary="List enrollment tokens issued for a node",
)
async def list_enrollment_tokens(
    node_id: str,
    service: Annotated[NodeService, Depends(get_node_service)],
) -> list[EnrollmentTokenResponse]:
    return await service.list_enrollment_tokens(node_id)


@router.post(
    "/{node_id}/enrollment-tokens/{token_id}/revoke",
    response_model=EnrollmentTokenResponse,
    summary="Revoke an active enrollment token",
)
async def revoke_enrollment_token(
    node_id: str,
    token_id: str,
    service: Annotated[NodeService, Depends(get_node_service)],
) -> EnrollmentTokenResponse:
    return await service.revoke_enrollment_token(node_id, token_id)


@settings_router.get(
    "/projects/{project_id}/settings",
    response_model=ProjectSettingsResponse,
    summary="Get telemetry profile settings for a project",
)
async def get_project_settings(
    project_id: str,
    service: Annotated[NodeService, Depends(get_node_service)],
) -> ProjectSettingsResponse:
    return await service.get_project_settings(project_id)


@settings_router.put(
    "/projects/{project_id}/settings",
    response_model=ProjectSettingsResponse,
    summary="Update telemetry profile settings for all nodes in a project",
)
async def update_project_settings(
    project_id: str,
    request: ProjectSettingsUpdateRequest,
    service: Annotated[NodeService, Depends(get_node_service)],
) -> ProjectSettingsResponse:
    return await service.update_project_settings(project_id, request)


@settings_router.put(
    "/nodes/{node_id}/settings",
    response_model=ProjectSettingsResponse,
    summary="Update telemetry profile settings for a specific node",
)
async def update_node_settings(
    node_id: str,
    request: ProjectSettingsUpdateRequest,
    service: Annotated[NodeService, Depends(get_node_service)],
) -> ProjectSettingsResponse:
    return await service.update_node_settings(node_id, request)
