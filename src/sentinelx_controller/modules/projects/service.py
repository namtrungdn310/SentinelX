"""Service layer for Project operations."""

import uuid

from fastapi import HTTPException, status

from sentinelx_common.contracts.projects import (
    LBAlgorithmType,
    ProjectCreateRequest,
    ProjectLBConfigContract,
    ProjectResponse,
    ProjectUpdateRequest,
)
from sentinelx_controller.modules.projects.models import ProjectModel
from sentinelx_controller.modules.projects.repository import ProjectRepository


class ProjectService:
    """Business logic for Project management."""

    def __init__(self, repository: ProjectRepository) -> None:
        self._repo = repository

    async def create_project(self, request: ProjectCreateRequest) -> ProjectResponse:
        """Create a new project and check for duplicate name."""
        name = request.name.strip()
        if not name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Project name cannot be empty",
            )
        existing = await self._repo.get_by_name(name)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project with name '{name}' already exists",
            )

        lb_cfg = request.load_balancer or ProjectLBConfigContract()
        description = (
            request.description.strip() or None
            if request.description is not None
            else None
        )
        model = await self._repo.create(
            name=name,
            description=description,
            lb_config=lb_cfg.model_dump(mode="json"),
        )
        return self._to_response(model)

    async def update_project(
        self,
        project_id_str: str,
        request: ProjectUpdateRequest,
    ) -> ProjectResponse:
        """Update project name, description, or Load Balancer configuration."""
        p_uuid = self._parse_uuid(project_id_str)
        model = await self._repo.get_by_id(p_uuid)
        if model is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id_str}' not found",
            )
        if request.name is not None:
            cleaned_name = request.name.strip()
            if not cleaned_name:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Project name cannot be empty",
                )
            if cleaned_name != model.name:
                duplicate = await self._repo.get_by_name(cleaned_name)
                if duplicate is not None and duplicate.id != model.id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Project with name '{cleaned_name}' already exists",
                    )
                model.name = cleaned_name
        if "description" in request.model_fields_set:
            model.description = (request.description or "").strip() or None
        if request.load_balancer is not None:
            model.lb_config = request.load_balancer.model_dump(mode="json")

        saved = await self._repo.save(model)
        return self._to_response(saved)

    async def update_lb_config(
        self,
        project_id_str: str,
        config: ProjectLBConfigContract,
    ) -> ProjectResponse:
        """Persist updated Load Balancer settings for a project."""
        return await self.update_project(
            project_id_str,
            ProjectUpdateRequest(load_balancer=config),
        )

    async def update_lb_algorithm(
        self,
        project_id_str: str,
        algorithm: LBAlgorithmType,
    ) -> ProjectResponse:
        """Update only the LB routing algorithm on a project."""
        current = await self.get_project(project_id_str)
        if not current.load_balancer.enabled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Load Balancer is not enabled for this project",
            )
        updated_cfg = current.load_balancer.model_copy(update={"algorithm": algorithm})
        return await self.update_lb_config(project_id_str, updated_cfg)

    async def get_project(self, project_id_str: str) -> ProjectResponse:
        """Get project details by project ID."""
        p_uuid = self._parse_uuid(project_id_str)

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
    def _parse_uuid(project_id_str: str) -> uuid.UUID:
        try:
            return uuid.UUID(project_id_str)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid project UUID format",
            ) from err

    @staticmethod
    def _to_response(model: ProjectModel) -> ProjectResponse:
        raw_lb = getattr(model, "lb_config", None) or {}
        lb_cfg = (
            ProjectLBConfigContract.model_validate(raw_lb)
            if isinstance(raw_lb, dict) and raw_lb
            else ProjectLBConfigContract()
        )
        return ProjectResponse(
            project_id=str(model.id),
            name=model.name,
            description=model.description,
            load_balancer=lb_cfg,
            created_at=model.created_at,
        )
