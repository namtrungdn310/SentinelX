"""Service layer for Node operations."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastapi import HTTPException, status

from sentinelx_common.contracts.agents import (
    AgentEnrollRequest,
    AgentEnrollResponse,
    EnrollmentStatus,
    EnrollmentTokenCreateRequest,
    EnrollmentTokenResponse,
    HeartbeatRequest,
    HeartbeatResponse,
)
from sentinelx_common.contracts.defense import AgentCommandContract
from sentinelx_common.contracts.nodes import (
    NodeLBRoleType,
    NodeRegisterRequest,
    NodeResponse,
    NodeStatus,
    NodeUpdateRequest,
)
from sentinelx_common.contracts.projects import (
    ProjectSettingsResponse,
    ProjectSettingsUpdateRequest,
    TelemetryProfileType,
)
from sentinelx_common.contracts.realtime import RealtimeEventType, RealtimeMessage
from sentinelx_common.utils.time import ensure_utc
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub
from sentinelx_controller.infrastructure.realtime.publisher import CommittedPublisher
from sentinelx_controller.modules.nodes.models import AgentEnrollmentModel, NodeModel
from sentinelx_controller.modules.nodes.repository import (
    AgentEnrollmentRepository,
    NodeRepository,
)
from sentinelx_controller.modules.projects.service import ProjectService

_PROFILE_CADENCE: dict[str, tuple[int, float]] = {
    "balanced": (7, 5.0),
    "high_sensitivity": (3, 2.0),
    "resource_saving": (10, 10.0),
}
_VALID_PROFILES: set[str] = set(_PROFILE_CADENCE)
_STALE_HEARTBEAT_SECONDS = 60


class NodeService:
    """Business logic for Node directory management."""

    def __init__(
        self,
        node_repo: NodeRepository,
        project_service: ProjectService,
        enrollment_repo: AgentEnrollmentRepository | None = None,
        *,
        realtime_hub: RealtimeHub | None = None,
        publisher: CommittedPublisher | None = None,
    ) -> None:
        self._node_repo = node_repo
        self._project_service = project_service
        self._enrollment_repo = enrollment_repo
        self._realtime_hub = realtime_hub
        self._publisher = publisher

    @staticmethod
    def _sanitize_hardware(raw: dict[str, int] | None) -> dict[str, int] | None:
        if not isinstance(raw, dict):
            return None
        cleaned: dict[str, int] = {}
        for key in ("cpu_cores", "total_memory_bytes", "total_disk_bytes"):
            val = raw.get(key)
            if isinstance(val, int) and not isinstance(val, bool) and val > 0:
                cleaned[key] = val
        return cleaned or None

    async def _broadcast_node_status(
        self,
        node: NodeModel,
        node_status: NodeStatus,
        *,
        timestamp: datetime,
    ) -> None:
        msg = RealtimeMessage(
            event=RealtimeEventType.NODE_STATUS.value,
            data={
                "node_id": str(node.id),
                "project_id": str(node.project_id),
                "hostname": node.hostname,
                "status": node_status.value,
                "last_seen": ensure_utc(node.last_seen_at).isoformat()
                if node.last_seen_at
                else timestamp.isoformat(),
            },
            timestamp=timestamp,
        )
        if self._publisher is not None:
            self._publisher.enqueue(msg)
        elif self._realtime_hub is not None:
            await self._realtime_hub.broadcast(msg)

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
            lb_role=request.lb_role,
            lb_backend_port=request.lb_backend_port,
            lb_health_path=request.lb_health_path,
        )
        return self._to_response(node)

    async def update_node(
        self,
        node_id_str: str,
        request: NodeUpdateRequest,
    ) -> NodeResponse:
        """Update node metadata or Load Balancer backend participation settings."""
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

        if request.hostname is not None:
            node.hostname = request.hostname.strip()
        if request.os_info is not None:
            node.os_info = request.os_info.strip() or None
        if request.lb_role is not None:
            node.lb_role = request.lb_role
        if request.lb_backend_port is not None:
            node.lb_backend_port = request.lb_backend_port
        if request.lb_health_path is not None:
            node.lb_health_path = request.lb_health_path.strip() or None

        await self._node_repo.save(node)
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
        hw = self._sanitize_hardware(request.hardware_info)
        if hw is not None:
            caps = dict(node.agent_capabilities or {})
            caps["hardware"] = hw
            node.agent_capabilities = caps
            await self._node_repo.save(node)

        await self._broadcast_node_status(node, NodeStatus.ONLINE, timestamp=now)

        return AgentEnrollResponse(
            agent_id=str(agent_id),
            node_id=str(node.id),
            status="enrolled",
            heartbeat_interval_seconds=7,
            enrolled_at=now,
        )

    async def process_heartbeat(
        self,
        request: HeartbeatRequest,
        commands: list[AgentCommandContract] | None = None,
    ) -> HeartbeatResponse:
        """Process heartbeat from an Agent and update node online status."""
        repo = self._ensure_enrollment_repo()
        try:
            n_uuid = uuid.UUID(request.node_id)
            a_uuid = uuid.UUID(request.agent_id)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid UUID format in heartbeat request",
            ) from err

        node = await self._node_repo.get_by_id(n_uuid)
        if node is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Node '{request.node_id}' not found",
            )

        is_valid = await repo.verify_agent_credentials(node_id=n_uuid, agent_id=a_uuid)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Agent credentials invalid or not enrolled for this node",
            )

        prev_effective = self._effective_status(node)
        now = datetime.now(UTC)
        await self._node_repo.record_heartbeat(node_id=n_uuid, last_seen_at=now)
        existing_caps = dict(node.agent_capabilities or {})
        new_caps: dict[str, Any] = {
            "protocol_version": request.command_protocol_version,
            "executor_mode": request.executor_mode,
            "supported_actions": request.supported_actions,
        }
        saved_settings = existing_caps.get("settings")
        if isinstance(saved_settings, dict):
            new_caps["settings"] = saved_settings
        hw = self._sanitize_hardware(request.hardware_info) or existing_caps.get("hardware")
        if isinstance(hw, dict):
            new_caps["hardware"] = hw
        node.agent_capabilities = new_caps
        await self._node_repo.save(node)

        if prev_effective != NodeStatus.ONLINE:
            await self._broadcast_node_status(node, NodeStatus.ONLINE, timestamp=now)

        profile = saved_settings.get("active_profile") if isinstance(saved_settings, dict) else None
        next_hb, telemetry_iv = _PROFILE_CADENCE.get(str(profile), (7, None))

        return HeartbeatResponse(
            status="ok",
            received_at=now,
            next_interval_seconds=next_hb,
            telemetry_interval_seconds=telemetry_iv,
            commands=commands or [],
        )

    @staticmethod
    def _build_node_settings_dict(
        profile: TelemetryProfileType,
        updated_at: datetime,
        updated_by: str,
    ) -> dict[str, str]:
        return {
            "active_profile": profile,
            "updated_at": updated_at.isoformat(),
            "updated_by": updated_by,
        }

    async def get_project_settings(self, project_id_str: str) -> ProjectSettingsResponse:
        """Read persisted telemetry profile settings for a project from its nodes."""
        await self._project_service.get_project(project_id_str)
        p_uuid = uuid.UUID(project_id_str)
        nodes = await self._node_repo.list_by_project(p_uuid)
        best_profile: TelemetryProfileType = "balanced"
        best_updated_at: datetime | None = None
        best_updated_by = "system"

        for node in nodes:
            caps = node.agent_capabilities or {}
            settings = caps.get("settings") if isinstance(caps, dict) else None
            if not isinstance(settings, dict):
                continue
            prof = settings.get("active_profile")
            if prof not in _VALID_PROFILES:
                continue
            raw_ts = settings.get("updated_at")
            try:
                ts = (
                    ensure_utc(datetime.fromisoformat(raw_ts))
                    if isinstance(raw_ts, str)
                    else ensure_utc(node.created_at)
                )
            except ValueError:
                ts = ensure_utc(node.created_at)
            if best_updated_at is None or ts >= best_updated_at:
                best_updated_at = ts
                best_profile = cast(TelemetryProfileType, prof)
                best_updated_by = str(settings.get("updated_by") or "admin@sentinelx.com")

        return ProjectSettingsResponse(
            project_id=project_id_str,
            active_profile=best_profile,
            updated_at=best_updated_at or datetime.now(UTC),
            updated_by=best_updated_by,
        )

    async def update_project_settings(
        self,
        project_id_str: str,
        request: ProjectSettingsUpdateRequest,
    ) -> ProjectSettingsResponse:
        """Persist telemetry profile settings across all nodes in a project."""
        await self._project_service.get_project(project_id_str)
        p_uuid = uuid.UUID(project_id_str)
        now = datetime.now(UTC)
        settings_dict = self._build_node_settings_dict(
            request.active_profile,
            now,
            request.updated_by,
        )
        nodes = await self._node_repo.list_by_project(p_uuid)
        for node in nodes:
            caps = dict(node.agent_capabilities or {})
            caps["settings"] = settings_dict
            node.agent_capabilities = caps
            await self._node_repo.save(node)

        return ProjectSettingsResponse(
            project_id=project_id_str,
            active_profile=request.active_profile,
            updated_at=now,
            updated_by=request.updated_by,
        )

    async def update_node_settings(
        self,
        node_id_str: str,
        request: ProjectSettingsUpdateRequest,
    ) -> ProjectSettingsResponse:
        """Persist telemetry profile settings for a single node."""
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
        now = datetime.now(UTC)
        caps = dict(node.agent_capabilities or {})
        caps["settings"] = self._build_node_settings_dict(
            request.active_profile,
            now,
            request.updated_by,
        )
        node.agent_capabilities = caps
        await self._node_repo.save(node)

        return ProjectSettingsResponse(
            project_id=str(node.project_id),
            node_id=str(node.id),
            active_profile=request.active_profile,
            updated_at=now,
            updated_by=request.updated_by,
        )

    async def verify_agent(self, node_id_str: str, agent_id_str: str) -> bool:
        """Public method to verify if an agent_id is valid and active for a node."""
        repo = self._ensure_enrollment_repo()
        try:
            n_uuid = uuid.UUID(node_id_str)
            a_uuid = uuid.UUID(agent_id_str)
        except ValueError:
            return False

        node = await self._node_repo.get_by_id(n_uuid)
        if node is None:
            return False

        return await repo.verify_agent_credentials(node_id=n_uuid, agent_id=a_uuid)

    def _ensure_enrollment_repo(self) -> AgentEnrollmentRepository:
        if self._enrollment_repo is None:
            raise RuntimeError("AgentEnrollmentRepository is not configured on NodeService")
        return self._enrollment_repo

    @staticmethod
    def _effective_status(model: NodeModel, now: datetime | None = None) -> NodeStatus:
        effective_status = NodeStatus(model.status)
        current_time = now or datetime.now(UTC)
        if (
            effective_status == NodeStatus.ONLINE
            and model.last_seen_at is not None
            and (current_time - ensure_utc(model.last_seen_at)).total_seconds()
            > _STALE_HEARTBEAT_SECONDS
        ):
            return NodeStatus.OFFLINE
        return effective_status

    async def sweep_stale_offline_nodes(
        self,
        *,
        now: datetime | None = None,
    ) -> list[str]:
        """Mark nodes whose heartbeat timed out as OFFLINE and emit realtime status updates."""
        current_time = now or datetime.now(UTC)
        transitioned: list[str] = []
        nodes = await self._node_repo.list_all()
        for node in nodes:
            if (
                node.status == NodeStatus.ONLINE.value
                and self._effective_status(node, now=current_time) == NodeStatus.OFFLINE
            ):
                node.status = NodeStatus.OFFLINE.value
                await self._node_repo.save(node)
                await self._broadcast_node_status(node, NodeStatus.OFFLINE, timestamp=current_time)
                transitioned.append(str(node.id))
        return transitioned

    @classmethod
    def _to_response(cls, model: NodeModel) -> NodeResponse:
        effective_status = cls._effective_status(model)
        raw_role = getattr(model, "lb_role", "standalone")
        lb_role: NodeLBRoleType = "lb_backend" if raw_role == "lb_backend" else "standalone"
        return NodeResponse(
            node_id=str(model.id),
            project_id=str(model.project_id),
            hostname=model.hostname,
            ip_address=model.ip_address,
            status=effective_status,
            os_info=model.os_info,
            lb_role=lb_role,
            lb_backend_port=getattr(model, "lb_backend_port", 8080) or 8080,
            lb_health_path=getattr(model, "lb_health_path", None),
            last_seen=ensure_utc(model.last_seen_at) if model.last_seen_at else None,
            created_at=ensure_utc(model.created_at),
            agent_capabilities=model.agent_capabilities or {},
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
