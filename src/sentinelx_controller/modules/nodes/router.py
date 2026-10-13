"""API router for node endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_common.contracts.nodes import NodeRegisterRequest, NodeResponse
from sentinelx_controller.infrastructure.database.session import get_db_session
from sentinelx_controller.modules.nodes.repository import NodeRepository
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
    return NodeService(node_repo=node_repo, project_service=project_service)


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
