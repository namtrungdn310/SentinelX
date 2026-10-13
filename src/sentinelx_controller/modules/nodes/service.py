"""Service layer for Node operations."""

import uuid

from fastapi import HTTPException, status

from sentinelx_common.contracts.nodes import NodeRegisterRequest, NodeResponse, NodeStatus
from sentinelx_controller.modules.nodes.models import NodeModel
from sentinelx_controller.modules.nodes.repository import NodeRepository
from sentinelx_controller.modules.projects.repository import ProjectRepository


class NodeService:
    """Nghiệp vụ quản lý danh bạ Node."""

    def __init__(
        self,
        node_repo: NodeRepository,
        project_repo: ProjectRepository,
    ) -> None:
        self._node_repo = node_repo
        self._project_repo = project_repo

    async def register_node(self, request: NodeRegisterRequest) -> NodeResponse:
        """Đăng ký node mới vào project đã tồn tại."""
        try:
            p_uuid = uuid.UUID(request.project_id)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid project_id UUID format",
            ) from err

        # Xác thực project tồn tại
        project = await self._project_repo.get_by_id(p_uuid)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{request.project_id}' not found",
            )

        # Xác thực tính duy nhất của IP trong project
        existing = await self._node_repo.get_by_ip_in_project(p_uuid, request.ip_address)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Node with IP '{request.ip_address}' already registered in this project",
            )

        node = await self._node_repo.create(
            project_id=p_uuid,
            hostname=request.hostname,
            ip_address=request.ip_address,
            os_info=request.os_info,
        )
        return self._to_response(node)

    async def get_node(self, node_id_str: str) -> NodeResponse:
        """Lấy thông tin node theo ID."""
        try:
            n_uuid = uuid.UUID(node_id_str)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid node UUID format",
            ) from err

        node = await self._node_repo.get_by_id(n_uuid)
        if node is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Node '{node_id_str}' not found",
            )
        return self._to_response(node)

    async def list_nodes(self, project_id_str: str | None = None) -> list[NodeResponse]:
        """Liệt kê danh sách nodes (hỗ trợ lọc theo project)."""
        if project_id_str is not None:
            try:
                p_uuid = uuid.UUID(project_id_str)
            except ValueError as err:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid project_id UUID format",
                ) from err
            nodes = await self._node_repo.list_by_project(p_uuid)
        else:
            nodes = await self._node_repo.list_all()

        return [self._to_response(n) for n in nodes]

    @staticmethod
    def _to_response(model: NodeModel) -> NodeResponse:
        return NodeResponse(
            node_id=str(model.id),
            project_id=str(model.project_id),
            hostname=model.hostname,
            ip_address=model.ip_address,
            status=NodeStatus(model.status),
            os_info=model.os_info,
            last_seen=model.last_seen_at,
            created_at=model.created_at,
        )
