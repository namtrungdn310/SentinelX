"""Application service for managing Defense Actions and Command Pipeline."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status

from sentinelx_common.contracts.defense import (
    AgentCommandContract,
    CommandAckRequest,
    CommandAckResponse,
    DefenseActionListResponse,
    DefenseActionResponse,
    DefenseActionStatus,
    ManualDefenseActionCreateRequest,
)
from sentinelx_common.contracts.incidents import IncidentStatus
from sentinelx_common.contracts.realtime import RealtimeEventType, RealtimeMessage
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub
from sentinelx_controller.infrastructure.realtime.publisher import CommittedPublisher
from sentinelx_controller.modules.defense.models import DefenseActionModel
from sentinelx_controller.modules.defense.repository import DefenseRepository
from sentinelx_controller.modules.incidents.repository import IncidentRepository

logger = logging.getLogger("sentinelx_controller.defense.service")


class DefenseService:
    """Service handling defense action authorization, command delivery, and ACK processing."""

    def __init__(
        self,
        defense_repo: DefenseRepository,
        realtime_hub: RealtimeHub | None = None,
        publisher: CommittedPublisher | None = None,
        incident_repo: IncidentRepository | None = None,
    ) -> None:
        self._repo = defense_repo
        self._realtime_hub = realtime_hub
        self._publisher = publisher
        self._incident_repo = incident_repo

    def _to_response(self, model: DefenseActionModel) -> DefenseActionResponse:
        return DefenseActionResponse(
            id=str(model.id),
            incident_id=str(model.incident_id) if model.incident_id else None,
            policy_id=str(model.policy_id) if model.policy_id else None,
            node_id=str(model.node_id),
            action_type=model.action_type,
            target_ip=model.target_ip,
            command_payload=model.command_payload,
            status=DefenseActionStatus(model.status),
            agent_ack_at=model.agent_ack_at,
            error_message=model.error_message,
            created_at=model.created_at,
        )

    async def _broadcast(self, event_type: RealtimeEventType, payload: dict[str, Any]) -> None:
        msg = RealtimeMessage(
            event=event_type.value,
            data=payload,
            timestamp=datetime.now(UTC),
        )
        if self._publisher is not None:
            self._publisher.enqueue(msg)
        elif self._realtime_hub is not None:
            await self._realtime_hub.broadcast(msg)

    async def create_action_from_policy(
        self,
        node_id: uuid.UUID,
        action_type: str,
        target_ip: str | None = None,
        command_payload: dict[str, Any] | None = None,
        incident_id: uuid.UUID | None = None,
        policy_id: uuid.UUID | None = None,
    ) -> DefenseActionResponse | None:
        """Create a defense action triggered automatically by PolicyEngine."""
        # 1. Duplicate check: Avoid stacking identical active actions
        if await self._repo.has_active_action(node_id, action_type, target_ip):
            logger.info(
                "Duplicate active action suppressed: node=%s type=%s target=%s",
                node_id,
                action_type,
                target_ip,
            )
            return None

        now = datetime.now(UTC)
        action = DefenseActionModel(
            id=uuid.uuid4(),
            incident_id=incident_id,
            policy_id=policy_id,
            node_id=node_id,
            action_type=action_type,
            target_ip=target_ip,
            command_payload=command_payload or {},
            status=DefenseActionStatus.PENDING.value,
            created_at=now,
        )
        saved = await self._repo.create_action(action)
        resp = self._to_response(saved)
        await self._broadcast(
            RealtimeEventType.DEFENSE_ACTION_CREATED,
            resp.model_dump(mode="json"),
        )
        return resp

    async def create_manual_action(
        self,
        request: ManualDefenseActionCreateRequest,
    ) -> DefenseActionResponse:
        """Create a defense action manually initiated by operator/dashboard."""
        try:
            node_uuid = uuid.UUID(request.node_id)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid node UUID format",
            ) from err

        inc_uuid: uuid.UUID | None = None
        if request.incident_id:
            try:
                inc_uuid = uuid.UUID(request.incident_id)
            except ValueError as err:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid incident UUID format",
                ) from err

        now = datetime.now(UTC)
        action = DefenseActionModel(
            id=uuid.uuid4(),
            incident_id=inc_uuid,
            policy_id=None,
            node_id=node_uuid,
            action_type=request.action_type.value,
            target_ip=request.target_ip,
            command_payload=request.command_payload,
            status=DefenseActionStatus.PENDING.value,
            created_at=now,
        )
        saved = await self._repo.create_action(action)
        resp = self._to_response(saved)
        await self._broadcast(
            RealtimeEventType.DEFENSE_ACTION_CREATED,
            resp.model_dump(mode="json"),
        )
        return resp

    async def get_action(self, action_id_str: str) -> DefenseActionResponse:
        """Get single defense action by UUID string."""
        try:
            action_uuid = uuid.UUID(action_id_str)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid action UUID format",
            ) from err

        action = await self._repo.get_by_id(action_uuid)
        if action is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Defense action not found",
            )
        return self._to_response(action)

    async def list_actions(
        self,
        node_id_str: str | None = None,
        incident_id_str: str | None = None,
        status_filter: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> DefenseActionListResponse:
        """List defense actions with optional filters and pagination."""
        node_uuid: uuid.UUID | None = None
        if node_id_str:
            try:
                node_uuid = uuid.UUID(node_id_str)
            except ValueError as err:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid node UUID format",
                ) from err

        inc_uuid: uuid.UUID | None = None
        if incident_id_str:
            try:
                inc_uuid = uuid.UUID(incident_id_str)
            except ValueError as err:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid incident UUID format",
                ) from err

        total, items = await self._repo.list_actions(
            node_id=node_uuid,
            incident_id=inc_uuid,
            status=status_filter,
            limit=limit,
            offset=offset,
        )
        return DefenseActionListResponse(
            total=total,
            items=[self._to_response(item) for item in items],
        )

    async def get_pending_commands_for_node(
        self,
        node_id: uuid.UUID,
    ) -> list[AgentCommandContract]:
        """Fetch pending commands for heartbeat piggyback and transition to SENT."""
        actions = await self._repo.get_and_mark_pending_commands(node_id=node_id)
        commands: list[AgentCommandContract] = []
        for a in actions:
            commands.append(
                AgentCommandContract(
                    id=str(a.id),
                    action_type=a.action_type,
                    target_ip=a.target_ip,
                    command_payload=a.command_payload,
                    created_at=a.created_at,
                )
            )
        return commands

    async def record_ack(
        self,
        action_id_str: str,
        request: CommandAckRequest,
    ) -> CommandAckResponse:
        """Record execution ACK received from Agent."""
        try:
            action_uuid = uuid.UUID(action_id_str)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid action UUID format",
            ) from err

        action = await self._repo.get_by_id(action_uuid)
        if action is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Defense action not found",
            )

        now = datetime.now(UTC)
        # Idempotent ACK handling
        if action.status == request.status.value and action.agent_ack_at is not None:
            return CommandAckResponse(
                status="ok",
                action_id=action_id_str,
                acknowledged_at=action.agent_ack_at,
            )

        updated = await self._repo.record_ack(
            action=action,
            status=request.status.value,
            agent_ack_at=now,
            error_message=request.error_message,
        )

        # Transition associated incident to MITIGATING when action is confirmed APPLIED
        if (
            action.incident_id is not None
            and self._incident_repo is not None
            and request.status == DefenseActionStatus.APPLIED
        ):
            inc = await self._incident_repo.get_by_id(action.incident_id)
            if inc and inc.status == IncidentStatus.DETECTED.value:
                inc.status = IncidentStatus.MITIGATING.value
                await self._incident_repo.save(inc)

        resp = self._to_response(updated)
        await self._broadcast(
            RealtimeEventType.DEFENSE_ACTION_UPDATED,
            resp.model_dump(mode="json"),
        )

        return CommandAckResponse(
            status="ok",
            action_id=action_id_str,
            acknowledged_at=now,
        )
