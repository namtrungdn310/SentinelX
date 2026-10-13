"""Repository for node persistence operations."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelx_common.contracts.nodes import NodeStatus
from sentinelx_controller.modules.nodes.models import NodeModel


class NodeRepository:
    """Xử lý truy vấn CSDL cho thực thể Node."""

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
        """Tạo bản ghi Node mới trong CSDL."""
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
        """Lấy thông tin Node theo UUID."""
        stmt = select(NodeModel).where(NodeModel.id == node_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_ip_in_project(
        self, project_id: uuid.UUID, ip_address: str
    ) -> NodeModel | None:
        """Kiểm tra sự tồn tại của IP trong cùng 1 project."""
        stmt = select(NodeModel).where(
            NodeModel.project_id == project_id,
            NodeModel.ip_address == ip_address.strip(),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: uuid.UUID) -> Sequence[NodeModel]:
        """Lấy danh sách các nodes thuộc 1 project."""
        stmt = (
            select(NodeModel)
            .where(NodeModel.project_id == project_id)
            .order_by(NodeModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_all(self) -> Sequence[NodeModel]:
        """Lấy toàn bộ danh sách nodes trên hệ thống."""
        stmt = select(NodeModel).order_by(NodeModel.created_at.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()
