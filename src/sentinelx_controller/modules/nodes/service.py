"""Service layer for Node operations."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status

from sentinelx_common.contracts.agents import (
    AgentEnrollRequest,
    AgentEnrollResponse,
    EnrollmentStatus,
    EnrollmentTokenCreateRequest,
    EnrollmentTokenResponse,
)
from sentinelx_common.contracts.nodes import NodeRegisterRequest, NodeResponse, NodeStatus
from sentinelx_common.utils.time import ensure_utc
from sentinelx_controller.modules.nodes.models import AgentEnrollmentModel, NodeModel
from sentinelx_controller.modules.nodes.repository import (
    AgentEnrollmentRepository,
    NodeRepository,
)
from sentinelx_controller.modules.projects.service import ProjectService


class NodeService:
    """Business logic for Node directory management."""

    def __init__(
        self,
        node_repo: NodeRepository,
        project_service: ProjectService,
        enrollment_repo: AgentEnrollmentRepository | None = None,
    ) -> None:
        self._node_repo = node_repo
        self._project_service = project_service
        self._enrollment_repo = enrollment_repo

    async def register_node(self, request: NodeRegisterRequest) -> NodeResponse:
        """Register a new node into an existing project."""
        try:
            p_uuid = uuid.UUID(request.project_id)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid project_id UUID format",
            ) from err

        # Verify that project exists via public ProjectService
        await self._project_service.get_project(request.project_id)

        # Verify IP uniqueness within project
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
        """Get node details by node ID."""
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
        """List nodes with optional project filter."""
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

    async def create_enrollment_token(
        self,
        node_id_str: str,
        request: EnrollmentTokenCreateRequest,
    ) -> EnrollmentTokenResponse:
        """Create a new enrollment token for a managed node."""
        repo = self._ensure_enrollment_repo()
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

        raw_token = f"sx_enroll_{secrets.token_urlsafe(32)}"
        expires_at = datetime.now(UTC) + timedelta(hours=request.expires_in_hours)

        record = await repo.create_token(
            node_id=n_uuid,
            token=raw_token,
            expires_at=expires_at,
        )
        return self._to_token_response(record)

    async def revoke_enrollment_token(
        self,
        node_id_str: str,
        token_id_str: str,
    ) -> EnrollmentTokenResponse:
        """Revoke an active enrollment token."""
        repo = self._ensure_enrollment_repo()
        try:
            n_uuid = uuid.UUID(node_id_str)
            t_uuid = uuid.UUID(token_id_str)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid UUID format",
            ) from err

        record = await repo.get_by_id(t_uuid)
        if record is None or record.node_id != n_uuid:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Enrollment token '{token_id_str}' not found for node",
            )

        updated = await repo.mark_revoked(t_uuid)
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Failed to revoke enrollment token",
            )

        return self._to_token_response(updated)

    async def list_enrollment_tokens(
        self,
        node_id_str: str,
    ) -> list[EnrollmentTokenResponse]:
        """List all enrollment tokens issued for a node."""
        repo = self._ensure_enrollment_repo()
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

        records = await repo.list_by_node(n_uuid)
        return [self._to_token_response(r) for r in records]

    async def enroll_agent(self, request: AgentEnrollRequest) -> AgentEnrollResponse:
        """Enroll an Agent, validate token, and issue credentials."""
        repo = self._ensure_enrollment_repo()
        try:
            n_uuid = uuid.UUID(request.node_id)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid node UUID format",
            ) from err

        node = await self._node_repo.get_by_id(n_uuid)
        if node is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Node '{request.node_id}' not found",
            )

        record = await repo.get_by_token(request.enrollment_token)
        if record is None or record.node_id != n_uuid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid enrollment token for this node",
            )

        if record.status == EnrollmentStatus.REVOKED.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Enrollment token has been revoked",
            )

        if record.status == EnrollmentStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Enrollment token has already been used",
            )

        now = datetime.now(UTC)
        if now > ensure_utc(record.expires_at):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Enrollment token has expired",
            )

        # Issue new Agent identity credential
        agent_id = uuid.uuid4()
        await repo.mark_approved(
            token_id=record.id,
            agent_id=agent_id,
            enrolled_at=now,
        )

        # Update node metadata reported by Agent
        await self._node_repo.update_agent_metadata(
            node_id=n_uuid,
            agent_version=request.agent_version,
            hostname=request.hostname,
            os_info=request.os_info,
        )

        return AgentEnrollResponse(
            agent_id=str(agent_id),
            node_id=str(node.id),
            status="enrolled",
            heartbeat_interval_seconds=10,
            enrolled_at=now,
        )

    def _ensure_enrollment_repo(self) -> AgentEnrollmentRepository:
        if self._enrollment_repo is None:
            raise RuntimeError("AgentEnrollmentRepository is not configured on NodeService")
        return self._enrollment_repo

    @staticmethod
    def _to_response(model: NodeModel) -> NodeResponse:
        return NodeResponse(
            node_id=str(model.id),
            project_id=str(model.project_id),
            hostname=model.hostname,
            ip_address=model.ip_address,
            status=NodeStatus(model.status),
            os_info=model.os_info,
            last_seen=ensure_utc(model.last_seen_at) if model.last_seen_at else None,
            created_at=ensure_utc(model.created_at),
        )

    @staticmethod
    def _to_token_response(model: AgentEnrollmentModel) -> EnrollmentTokenResponse:
        return EnrollmentTokenResponse(
            token_id=str(model.id),
            node_id=str(model.node_id),
            enrollment_token=model.enrollment_token,
            status=EnrollmentStatus(model.status),
            expires_at=ensure_utc(model.expires_at),
            enrolled_at=ensure_utc(model.enrolled_at) if model.enrolled_at else None,
            created_at=ensure_utc(model.created_at),
        )


