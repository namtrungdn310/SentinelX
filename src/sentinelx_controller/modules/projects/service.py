"""Service layer for Project operations."""

import uuid

from fastapi import HTTPException, status

from sentinelx_common.contracts.projects import ProjectCreateRequest, ProjectResponse
from sentinelx_controller.modules.projects.models import ProjectModel
from sentinelx_controller.modules.projects.repository import ProjectRepository


class ProjectService:
    """Business logic for Project management."""

    def __init__(self, repository: ProjectRepository) -> None:
        self._repo = repository

    async def create_project(self, request: ProjectCreateRequest) -> ProjectResponse:
        """Create a new project and check for duplicate name."""
        existing = await self._repo.get_by_name(request.name)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project with name '{request.name}' already exists",
            )

        model = await self._repo.create(
            name=request.name,
            description=request.description,
        )
        return self._to_response(model)

    async def get_project(self, project_id_str: str) -> ProjectResponse:
        """Get project details by project ID."""
        try:
            p_uuid = uuid.UUID(project_id_str)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid project UUID format",
            ) from err

        model = await self._repo.get_by_id(p_uuid)
        if model is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id_str}' not found",
            )
        return self._to_response(model)

    async def list_projects(self) -> list[ProjectResponse]:
        """List all projects."""
        projects = await self._repo.list_all()
        return [self._to_response(p) for p in projects]

    @staticmethod
    def _to_response(model: ProjectModel) -> ProjectResponse:
        return ProjectResponse(
            project_id=str(model.id),
            name=model.name,
            description=model.description,
            created_at=model.created_at,
        )
