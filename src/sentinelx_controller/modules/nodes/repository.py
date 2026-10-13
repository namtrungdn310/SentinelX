"""Repository for node persistence operations."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_common.contracts.nodes import NodeStatus
from sentinelx_controller.modules.nodes.models import NodeModel


class NodeRepository:
    """Handle database queries for Node entity."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        project_id: uuid.UUID,
        hostname: str,
        ip_address: str,
        os_info: str | None = None,
        node_id: uuid.UUID | None = None,
    ) -> NodeModel:
        """Create a new Node record in database."""
        node = NodeModel(
            id=node_id or uuid.uuid4(),
            project_id=project_id,
            hostname=hostname.strip(),
            ip_address=ip_address.strip(),
            os_info=os_info.strip() if os_info else None,
            status=NodeStatus.UNENROLLED.value,
        )
        self._session.add(node)
        await self._session.flush()
        return node

    async def get_by_id(self, node_id: uuid.UUID) -> NodeModel | None:
        """Get a Node by its UUID."""
        stmt = select(NodeModel).where(NodeModel.id == node_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_ip_in_project(
        self, project_id: uuid.UUID, ip_address: str
    ) -> NodeModel | None:
        """Check if an IP address exists within a project."""
        stmt = select(NodeModel).where(
            NodeModel.project_id == project_id,
            NodeModel.ip_address == ip_address.strip(),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: uuid.UUID) -> Sequence[NodeModel]:
        """List nodes belonging to a project."""
        stmt = (
            select(NodeModel)
            .where(NodeModel.project_id == project_id)
            .order_by(NodeModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_all(self) -> Sequence[NodeModel]:
        """List all nodes across the system."""
        stmt = select(NodeModel).order_by(NodeModel.created_at.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()
