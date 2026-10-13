"""Repository for project persistence operations."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_controller.modules.projects.models import ProjectModel


class ProjectRepository:
    """Handle database queries for Project entity."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        name: str,
        description: str | None = None,
        project_id: uuid.UUID | None = None,
    ) -> ProjectModel:
        """Create a new Project record in database."""
        project = ProjectModel(
            id=project_id or uuid.uuid4(),
            name=name.strip(),
            description=description.strip() if description else None,
        )
        self._session.add(project)
        await self._session.flush()
        return project

    async def get_by_id(self, project_id: uuid.UUID) -> ProjectModel | None:
        """Get a Project by its UUID."""
        stmt = select(ProjectModel).where(ProjectModel.id == project_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> ProjectModel | None:
        """Get a Project by its unique name."""
        stmt = select(ProjectModel).where(ProjectModel.name == name.strip())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> Sequence[ProjectModel]:
        """Get list of all projects ordered by creation time."""
        stmt = select(ProjectModel).order_by(ProjectModel.created_at.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()
