"""API router for node endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_common.contracts.agents import (
    AgentEnrollRequest,
    AgentEnrollResponse,
    EnrollmentTokenCreateRequest,
    EnrollmentTokenResponse,
    HeartbeatRequest,
    HeartbeatResponse,
)
from sentinelx_common.contracts.nodes import NodeRegisterRequest, NodeResponse
from sentinelx_controller.infrastructure.database.session import get_db_session
from sentinelx_controller.modules.nodes.repository import (
    AgentEnrollmentRepository,
    NodeRepository,
)
from sentinelx_controller.modules.nodes.service import NodeService
from sentinelx_controller.modules.projects.router import get_project_service
from sentinelx_controller.modules.projects.service import ProjectService

router = APIRouter(prefix="/nodes", tags=["nodes"])


def get_node_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> NodeService:
    """Dependency providing NodeService."""
    node_repo = NodeRepository(session)
    enrollment_repo = AgentEnrollmentRepository(session)
    return NodeService(
        node_repo=node_repo,
        project_service=project_service,
        enrollment_repo=enrollment_repo,
    )


@router.post(
    "",
    response_model=NodeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new node into a project",
)
async def register_node(
    request: NodeRegisterRequest,
    service: Annotated[NodeService, Depends(get_node_service)],
) -> NodeResponse:
    return await service.register_node(request)


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
) -> HeartbeatResponse:
    return await service.process_heartbeat(request)



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

