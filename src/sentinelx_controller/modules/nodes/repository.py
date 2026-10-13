"""Repository for node persistence operations."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_common.contracts.agents import EnrollmentStatus
from sentinelx_common.contracts.nodes import NodeStatus
from sentinelx_controller.modules.nodes.models import AgentEnrollmentModel, NodeModel


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

    async def update_agent_metadata(
        self,
        node_id: uuid.UUID,
        agent_version: str | None = None,
        hostname: str | None = None,
        os_info: str | None = None,
    ) -> NodeModel | None:
        """Update node metadata reported by Agent upon enrollment."""
        node = await self.get_by_id(node_id)
        if node is None:
            return None

        if agent_version is not None:
            node.agent_version = agent_version.strip()
        if hostname is not None:
            node.hostname = hostname.strip()
        if os_info is not None:
            node.os_info = os_info.strip()

        await self._session.flush()
        return node


class AgentEnrollmentRepository:
    """Handle database operations for Agent enrollment tokens."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_token(
        self,
        node_id: uuid.UUID,
        token: str,
        expires_at: datetime,
        token_id: uuid.UUID | None = None,
    ) -> AgentEnrollmentModel:
        """Create a new enrollment token record."""
        record = AgentEnrollmentModel(
            id=token_id or uuid.uuid4(),
            node_id=node_id,
            enrollment_token=token.strip(),
            status=EnrollmentStatus.PENDING.value,
            expires_at=expires_at,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_by_token(self, token: str) -> AgentEnrollmentModel | None:
        """Get an enrollment record by its token string."""
        stmt = select(AgentEnrollmentModel).where(
            AgentEnrollmentModel.enrollment_token == token.strip()
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, token_id: uuid.UUID) -> AgentEnrollmentModel | None:
        """Get an enrollment record by its primary key UUID."""
        stmt = select(AgentEnrollmentModel).where(AgentEnrollmentModel.id == token_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_node(self, node_id: uuid.UUID) -> Sequence[AgentEnrollmentModel]:
        """List all enrollment tokens generated for a node."""
        stmt = (
            select(AgentEnrollmentModel)
            .where(AgentEnrollmentModel.node_id == node_id)
            .order_by(AgentEnrollmentModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def mark_approved(
        self,
        token_id: uuid.UUID,
        agent_id: uuid.UUID,
        enrolled_at: datetime,
    ) -> AgentEnrollmentModel | None:
        """Transition an enrollment token to APPROVED state upon successful enrollment."""
        record = await self.get_by_id(token_id)
        if record is None:
            return None

        record.status = EnrollmentStatus.APPROVED.value
        record.agent_id = agent_id
        record.enrolled_at = enrolled_at
        await self._session.flush()
        return record

    async def mark_revoked(self, token_id: uuid.UUID) -> AgentEnrollmentModel | None:
        """Revoke an active enrollment token."""
        record = await self.get_by_id(token_id)
        if record is None:
            return None

        record.status = EnrollmentStatus.REVOKED.value
        await self._session.flush()
        return record

