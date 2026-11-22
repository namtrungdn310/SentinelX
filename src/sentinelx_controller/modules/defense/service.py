"""Application service for managing Defense Actions and Command Pipeline."""

import ipaddress
import logging
import secrets
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status

from sentinelx_common.contracts.command_parameters import normalize_command
from sentinelx_common.contracts.defense import (
    AgentCommandContract,
    CommandAckRequest,
    CommandAckResponse,
    DefenseActionListResponse,
    DefenseActionResponse,
    DefenseActionStatus,
    ManualDefenseActionCreateRequest,
)
from sentinelx_common.contracts.realtime import RealtimeEventType, RealtimeMessage
from sentinelx_common.utils.time import ensure_utc
from sentinelx_controller.config import CoreSafetySettings
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub
from sentinelx_controller.infrastructure.realtime.publisher import CommittedPublisher
from sentinelx_controller.modules.defense.models import DefenseActionModel
from sentinelx_controller.modules.defense.repository import DefenseRepository
from sentinelx_controller.modules.incidents.service import IncidentService
from sentinelx_controller.modules.nodes.service import NodeService

logger = logging.getLogger("sentinelx_controller.defense.service")


RecoveryAckHandler = Callable[[DefenseActionResponse, str, str | None], Awaitable[None]]


class DefenseService:
    """Service handling defense action authorization, command delivery, and ACK processing."""

    def __init__(
        self,
        defense_repo: DefenseRepository,
        realtime_hub: RealtimeHub | None = None,
        publisher: CommittedPublisher | None = None,
        incident_service: IncidentService | None = None,
        recovery_ack_handler: RecoveryAckHandler | None = None,
        node_service: NodeService | None = None,
        safety: CoreSafetySettings | None = None,
    ) -> None:
        self._repo = defense_repo
        self._realtime_hub = realtime_hub
        self._publisher = publisher
        self._incidents = incident_service
        self._recovery_ack_handler = recovery_ack_handler
        self._nodes = node_service
        self._safety = safety or CoreSafetySettings()

    def attach_recovery_handler(self, handler: RecoveryAckHandler) -> None:
        self._recovery_ack_handler = handler

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
            expires_at=model.expires_at,
            applied_at=model.applied_at,
            effective_until=model.effective_until,
            attempts=model.attempts or 0,
            execution_metadata=model.execution_metadata or {},
        )

    async def _validate_target(
        self,
        node_id: uuid.UUID,
        action_type: str,
        target_ip: str | None,
        payload: dict[str, Any],
    ) -> tuple[str | None, dict[str, Any]]:
        try:
            if "effective_until" in payload:
                raise ValueError("effective_until is assigned only by the Agent execution journal")
            target, parameters = normalize_command(action_type, target_ip, payload)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        if target and action_type == "BLOCK_IP_NFTABLES":
            ip = ipaddress.ip_address(target)
            if ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_link_local:
                raise HTTPException(422, "Protected/non-unicast target")
            for cidr in self._safety.protected_cidrs:
                if ip in ipaddress.ip_network(cidr, strict=False):
                    raise HTTPException(422, "Target belongs to protected infrastructure")
            if self._nodes is not None:
                node = await self._nodes.get_node(str(node_id))
                if ip == ipaddress.ip_address(node.ip_address):
                    raise HTTPException(422, "Cannot block the node's own address")
        elif self._nodes is not None:
            await self._nodes.get_node(str(node_id))
        return target, parameters

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

    async def lock_node(self, node_id: uuid.UUID) -> None:
        await self._repo.lock_node(node_id)

    async def lock_action(self, action_id: uuid.UUID) -> DefenseActionResponse | None:
        model = await self._repo.lock_action(action_id)
        return self._to_response(model) if model is not None else None

    async def applied_actions(self, node_id: uuid.UUID | None) -> list[DefenseActionResponse]:
        return [
            self._to_response(a) for a in await self._repo.get_applied_blocking_actions(node_id)
        ]

    async def has_active_incident_actions(self, incident_id: uuid.UUID) -> bool:
        return await self._repo.has_active_blocking_actions_for_incident(incident_id)

    async def mark_reverted(self, action_id: uuid.UUID) -> None:
        model = await self._repo.lock_action(action_id)
        if model is not None and model.status == "APPLIED":
            model.status = "REVERTED"
            await self._broadcast(
                RealtimeEventType.DEFENSE_ACTION_REVERTED,
                self._to_response(model).model_dump(mode="json"),
            )

    async def queue_unblock(self, original: DefenseActionResponse) -> DefenseActionResponse:
        now = datetime.now(UTC)
        model = DefenseActionModel(
            id=uuid.uuid4(),
            node_id=uuid.UUID(original.node_id),
            incident_id=uuid.UUID(original.incident_id) if original.incident_id else None,
            policy_id=uuid.UUID(original.policy_id) if original.policy_id else None,
            action_type="UNBLOCK_IP_NFTABLES",
            target_ip=original.target_ip,
            command_payload={"original_defense_action_id": original.id},
            status="PENDING",
            created_at=now,
            expires_at=now + timedelta(seconds=self._safety.command_ttl_seconds),
        )
        saved = await self._repo.create_action(model)
        result = self._to_response(saved)
        await self._broadcast(
            RealtimeEventType.DEFENSE_ACTION_CREATED, result.model_dump(mode="json")
        )
        return result

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
        target_ip, parameters = await self._validate_target(
            node_id,
            action_type,
            target_ip,
            command_payload or {},
        )
        await self._repo.lock_node(node_id)
        # Serialized duplicate check includes manual and automatic actions.
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
            command_payload=parameters,
            status=DefenseActionStatus.PENDING.value,
            created_at=now,
            expires_at=now + timedelta(seconds=self._safety.command_ttl_seconds),
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

        if request.action_type.value == "UNBLOCK_IP_NFTABLES":
            raise HTTPException(422, "Use the recovery endpoint to unblock an owned action")
        if inc_uuid is not None and self._incidents is not None:
            await self._incidents.validate_action_context(inc_uuid, node_uuid)
        target, parameters = await self._validate_target(
            node_uuid,
            request.action_type.value,
            request.target_ip,
            request.command_payload,
        )
        await self._repo.lock_node(node_uuid)
        if await self._repo.has_active_action(node_uuid, request.action_type.value, target):
            raise HTTPException(409, "An active action already owns this target")
        now = datetime.now(UTC)
        action = DefenseActionModel(
            id=uuid.uuid4(),
            incident_id=inc_uuid,
            policy_id=None,
            node_id=node_uuid,
            action_type=request.action_type.value,
            target_ip=target,
            command_payload=parameters,
            status=DefenseActionStatus.PENDING.value,
            created_at=now,
            expires_at=now + timedelta(seconds=self._safety.command_ttl_seconds),
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

    async def cancel_pending(self, action_id: uuid.UUID) -> DefenseActionResponse:
        action = await self._repo.lock_action(action_id)
        if action is None:
            raise HTTPException(404, "Defense action not found")
        if action.status == "CANCELLED":
            return self._to_response(action)
        if action.status != "PENDING":
            raise HTTPException(
                409, "Only an undelivered command can be cancelled; recover applied blocks"
            )
        action.status = "CANCELLED"
        action.error_message = "Cancelled by operator before delivery"
        response = self._to_response(action)
        await self._broadcast(
            RealtimeEventType.DEFENSE_ACTION_UPDATED, response.model_dump(mode="json")
        )
        return response

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
        supported_actions: list[str] | None = None,
    ) -> list[AgentCommandContract]:
        """Fetch pending commands for heartbeat piggyback and transition to SENT."""
        actions = await self._repo.get_and_mark_pending_commands(
            node_id=node_id,
            lease_seconds=self._safety.command_lease_seconds,
            max_attempts=self._safety.command_max_attempts,
            supported_actions=supported_actions,
        )
        commands: list[AgentCommandContract] = []
        for a in actions:
            commands.append(
                AgentCommandContract(
                    id=str(a.id),
                    action_type=a.action_type,
                    target_ip=a.target_ip,
                    command_payload=a.command_payload,
                    created_at=a.created_at,
                    node_id=str(a.node_id),
                    expires_at=ensure_utc(a.expires_at),
                    delivery_token=a.delivery_token or "",
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

        if request.action_id != action_id_str:
            raise HTTPException(422, "Body action_id must match path action_id")
        if (
            self._nodes is None
            or not request.node_id
            or not request.agent_id
            or not await self._nodes.verify_agent(request.node_id, request.agent_id)
        ):
            raise HTTPException(403, "An enrolled Agent identity is required for ACK")
        action = await self._repo.lock_action(action_uuid)
        if action is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Defense action not found",
            )

        if str(action.node_id) != request.node_id:
            raise HTTPException(403, "Action belongs to another node")
        if not action.delivery_token or not secrets.compare_digest(
            action.delivery_token,
            request.delivery_token,
        ):
            raise HTTPException(409, "Missing or invalid command delivery token")
        now = datetime.now(UTC)
        # Idempotent ACK handling
        same_result = action.status == request.status.value or (
            action.status == "REVERTED" and request.status == DefenseActionStatus.APPLIED
        )
        if same_result and action.agent_ack_at is not None:
            if (
                action.execution_metadata != request.execution_metadata
                or action.error_message != request.error_message
                or action.executed_at is None
                or request.executed_at is None
                or ensure_utc(action.executed_at) != request.executed_at
            ):
                raise HTTPException(409, "Conflicting replay of a completed ACK")
            return CommandAckResponse(
                status="ok",
                action_id=action_id_str,
                acknowledged_at=action.agent_ack_at,
            )

        if action.status not in {"SENT", "EXPIRED"}:
            raise HTTPException(409, "Only a delivered, nonterminal command may be acknowledged")
        if action.status == "EXPIRED" and request.status == DefenseActionStatus.APPLIED:
            if await self._repo.has_active_action(
                action.node_id, action.action_type, action.target_ip
            ):
                raise HTTPException(
                    409, "Late receipt conflicts with a newer active action; reconcile host"
                )
        executed = request.executed_at
        if executed is None or executed > now + timedelta(seconds=30):
            raise HTTPException(422, "ACK requires a valid execution timestamp")
        if executed < ensure_utc(action.created_at) - timedelta(seconds=30):
            raise HTTPException(422, "Execution precedes command creation")
        if request.status == DefenseActionStatus.APPLIED:
            if executed > ensure_utc(action.expires_at):
                raise HTTPException(409, "Command was executed after expiry")
            if request.execution_metadata.get("executor") != "nftables":
                raise HTTPException(422, "APPLIED requires a real executor outcome")
            if request.execution_metadata.get("simulated") or request.execution_metadata.get(
                "noop"
            ):
                raise HTTPException(422, "Simulation cannot report APPLIED")
            action.applied_at = executed
            if action.action_type == "BLOCK_IP_NFTABLES":
                action.effective_until = executed + timedelta(
                    seconds=int(action.command_payload["duration_seconds"]),
                )
        action.execution_metadata = request.execution_metadata
        action.executed_at = executed
        action.leased_until = None

        updated = await self._repo.record_ack(
            action=action,
            status=request.status.value,
            agent_ack_at=now,
            error_message=request.error_message,
        )

        # Transition associated incident to MITIGATING when action is confirmed APPLIED
        if (
            action.incident_id is not None
            and self._incidents is not None
            and request.status == DefenseActionStatus.APPLIED
            and action.action_type != "UNBLOCK_IP_NFTABLES"
        ):
            action_note: str | None = None
            if action.action_type == "BLOCK_IP_NFTABLES" and action.target_ip:
                ttl_min = int(action.command_payload.get("duration_seconds", 0)) // 60
                action_note = (
                    f"nftables: DROP {action.target_ip} (thời hạn: {ttl_min} phút)"
                    if ttl_min > 0
                    else f"nftables: DROP {action.target_ip}"
                )
            elif action.action_type == "RESTART_SERVICE":
                svc = (
                    action.command_payload.get("service_name")
                    or action.command_payload.get("target")
                    or "service"
                )
                action_note = f"service: RESTART {svc}"
            elif action.action_type == "CLEAR_OS_CACHE":
                action_note = "os-cache: CLEAR"
            await self._incidents.mark_mitigating(action.incident_id, action_note=action_note)

        # Trigger recovery completion hook if unblock action was acknowledged
        if self._recovery_ack_handler is not None and action.action_type == "UNBLOCK_IP_NFTABLES":
            await self._recovery_ack_handler(
                self._to_response(action),
                request.status.value,
                request.error_message,
            )

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
