"""API router for project endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_common.contracts.projects import ProjectCreateRequest, ProjectResponse
from sentinelx_controller.infrastructure.database.session import get_db_session
from sentinelx_controller.modules.projects.repository import ProjectRepository
from sentinelx_controller.modules.projects.service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


def get_project_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectService:
    """Dependency that provides ProjectService with active database session."""
    repository = ProjectRepository(session)
    return ProjectService(repository)


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
)
async def create_project(
    request: ProjectCreateRequest,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    return await service.create_project(request)


@router.get(
    "",
    response_model=list[ProjectResponse],
    summary="List all projects",
)
async def list_projects(
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> list[ProjectResponse]:
    return await service.list_projects()


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project details by ID",
)
async def get_project(
    project_id: str,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    return await service.get_project(project_id)
