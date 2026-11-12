"""Application service for Recovery and Cooldown management."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status

from sentinelx_common.contracts.defense import DefenseActionStatus
from sentinelx_common.contracts.incidents import IncidentStatus
from sentinelx_common.contracts.realtime import RealtimeEventType, RealtimeMessage
from sentinelx_common.contracts.recovery import (
    RecoveryActionListResponse,
    RecoveryActionResponse,
    RecoveryActionType,
    RecoveryReason,
    RecoveryStatus,
)
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub
from sentinelx_controller.infrastructure.realtime.publisher import CommittedPublisher
from sentinelx_controller.modules.defense.models import DefenseActionModel
from sentinelx_controller.modules.defense.repository import DefenseRepository
from sentinelx_controller.modules.incidents.repository import IncidentRepository
from sentinelx_controller.modules.recovery.models import RecoveryActionModel
from sentinelx_controller.modules.recovery.repository import RecoveryRepository

logger = logging.getLogger("sentinelx_controller.recovery.service")


class RecoveryService:
    """Service orchestrating recovery, unblock actions, cooldowns, and incident resolution."""

    def __init__(
        self,
        recovery_repo: RecoveryRepository,
        defense_repo: DefenseRepository,
        incident_repo: IncidentRepository | None = None,
        realtime_hub: RealtimeHub | None = None,
        publisher: CommittedPublisher | None = None,
    ) -> None:
        self._recovery_repo = recovery_repo
        self._defense_repo = defense_repo
        self._incident_repo = incident_repo
        self._realtime_hub = realtime_hub
        self._publisher = publisher

    def _to_response(self, model: RecoveryActionModel) -> RecoveryActionResponse:
        return RecoveryActionResponse(
            id=str(model.id),
            defense_action_id=str(model.defense_action_id),
            reason=RecoveryReason(model.reason),
            status=RecoveryStatus(model.status),
            executed_at=model.executed_at,
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

    async def revert_defense_action(
        self,
        defense_action_id_str: str,
        reason: RecoveryReason = RecoveryReason.MANUAL_UNBLOCK,
    ) -> RecoveryActionResponse:
        """Trigger unblock / recovery for a stateful defense action."""
        try:
            action_uuid = uuid.UUID(defense_action_id_str)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid defense action UUID format",
            ) from err

        action = await self._defense_repo.get_by_id(action_uuid)
        if action is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Defense action not found",
            )

        # Idempotency: If already REVERTED, return existing recovery record
        if action.status == DefenseActionStatus.REVERTED.value:
            existing = await self._recovery_repo.get_by_defense_action_id(action.id)
            if existing is not None:
                return self._to_response(existing)

        # Check if already pending recovery
        existing_pending = await self._recovery_repo.get_by_defense_action_id(action.id)
        if existing_pending is not None and existing_pending.status == RecoveryStatus.PENDING.value:
            return self._to_response(existing_pending)

        now = datetime.now(UTC)

        # 1. Persist RecoveryAction record
        recovery = RecoveryActionModel(
            id=uuid.uuid4(),
            defense_action_id=action.id,
            reason=reason.value,
            status=RecoveryStatus.PENDING.value,
            executed_at=now,
        )
        await self._recovery_repo.create_recovery(recovery)

        # 2. Queue UNBLOCK_IP_NFTABLES command for Agent
        unblock_cmd = DefenseActionModel(
            id=uuid.uuid4(),
            incident_id=action.incident_id,
            policy_id=action.policy_id,
            node_id=action.node_id,
            action_type=RecoveryActionType.UNBLOCK_IP_NFTABLES.value,
            target_ip=action.target_ip,
            command_payload={
                "original_defense_action_id": str(action.id),
                "reason": reason.value,
            },
            status=DefenseActionStatus.PENDING.value,
            created_at=now,
        )
        await self._defense_repo.create_action(unblock_cmd)

        logger.info(
            "Triggered recovery for action=%s: unblock_cmd=%s target=%s reason=%s",
            action.id,
            unblock_cmd.id,
            action.target_ip,
            reason.value,
        )

        resp = self._to_response(recovery)
        await self._broadcast(
            RealtimeEventType.DEFENSE_ACTION_CREATED,
            {
                "id": str(unblock_cmd.id),
                "action_type": unblock_cmd.action_type,
                "target_ip": unblock_cmd.target_ip,
                "node_id": str(unblock_cmd.node_id),
                "status": unblock_cmd.status,
            },
        )
        return resp

    async def scan_and_revert_expired_actions(
        self,
        node_id: uuid.UUID | None = None,
    ) -> list[RecoveryActionResponse]:
        """Scan active APPLIED actions and trigger unblock if block_duration has elapsed."""
        applied_actions = await self._defense_repo.get_applied_blocking_actions(node_id=node_id)
        now = datetime.now(UTC)
        recovered: list[RecoveryActionResponse] = []

        for action in applied_actions:
            duration_sec = action.command_payload.get("block_duration_seconds", 1800)
            # An action with block_duration_seconds == 0 is permanent unless manually unblocked
            if duration_sec <= 0:
                continue

            created_at = action.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)

            if created_at + timedelta(seconds=duration_sec) <= now:
                existing = await self._recovery_repo.get_by_defense_action_id(action.id)
                if existing is None or existing.status == RecoveryStatus.FAILED.value:
                    logger.info(
                        "Action %s expired (created_at=%s, duration=%ds). Triggering recovery.",
                        action.id,
                        created_at,
                        duration_sec,
                    )
                    res = await self.revert_defense_action(
                        defense_action_id_str=str(action.id),
                        reason=RecoveryReason.TIMEOUT_EXPIRED,
                    )
                    recovered.append(res)

        return recovered

    async def handle_unblock_ack(
        self,
        unblock_action: DefenseActionModel,
        status_val: str,
        error_message: str | None = None,
    ) -> None:
        """Handle execution ACK for an UNBLOCK_IP_NFTABLES action."""
        orig_id_str = unblock_action.command_payload.get("original_defense_action_id")
        if not orig_id_str:
            return

        try:
            orig_uuid = uuid.UUID(orig_id_str)
        except ValueError:
            return

        now = datetime.now(UTC)
        recovery = await self._recovery_repo.get_by_defense_action_id(orig_uuid)

        if status_val == DefenseActionStatus.APPLIED.value:
            # Mark original defense action as REVERTED
            orig_action = await self._defense_repo.get_by_id(orig_uuid)
            if orig_action is not None:
                orig_action.status = DefenseActionStatus.REVERTED.value
                await self._defense_repo.record_ack(
                    action=orig_action,
                    status=DefenseActionStatus.REVERTED.value,
                    agent_ack_at=now,
                    error_message=None,
                )

            # Mark recovery action as SUCCESS
            if recovery is not None:
                recovery.status = RecoveryStatus.SUCCESS.value
                recovery.executed_at = now
                await self._recovery_repo.save(recovery)
                await self._broadcast(
                    RealtimeEventType.RECOVERY_COMPLETED,
                    self._to_response(recovery).model_dump(mode="json"),
                )

            # Broadcast defense action reverted
            if orig_action is not None:
                await self._broadcast(
                    RealtimeEventType.DEFENSE_ACTION_REVERTED,
                    {
                        "id": str(orig_action.id),
                        "node_id": str(orig_action.node_id),
                        "target_ip": orig_action.target_ip,
                        "status": orig_action.status,
                    },
                )

                # Check if associated Incident can transition to RESOLVED
                if orig_action.incident_id is not None and self._incident_repo is not None:
                    has_active = (
                        await self._defense_repo.has_active_blocking_actions_for_incident(
                            orig_action.incident_id
                        )
                    )
                    if not has_active:
                        inc = await self._incident_repo.get_by_id(orig_action.incident_id)
                        if inc is not None and inc.status in (
                            IncidentStatus.DETECTED.value,
                            IncidentStatus.MITIGATING.value,
                        ):
                            inc.status = IncidentStatus.RESOLVED.value
                            inc.resolved_at = now
                            await self._incident_repo.save(inc)
                            logger.info(
                                "Incident %s resolved after all defense actions reverted",
                                inc.id,
                            )
                            await self._broadcast(
                                RealtimeEventType.INCIDENT_UPDATE,
                                {
                                    "id": str(inc.id),
                                    "status": inc.status,
                                    "resolved_at": inc.resolved_at.isoformat(),
                                },
                            )
        else:
            # Unblock execution failed on Agent
            if recovery is not None:
                recovery.status = RecoveryStatus.FAILED.value
                recovery.executed_at = now
                await self._recovery_repo.save(recovery)

    async def get_recovery(self, recovery_id_str: str) -> RecoveryActionResponse:
        """Get single recovery action by ID."""
        try:
            r_uuid = uuid.UUID(recovery_id_str)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid recovery action UUID format",
            ) from err

        rec = await self._recovery_repo.get_by_id(r_uuid)
        if rec is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recovery action not found",
            )
        return self._to_response(rec)

    async def list_recoveries(
        self,
        status_filter: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> RecoveryActionListResponse:
        """List recovery actions with optional status filter and pagination."""
        total, items = await self._recovery_repo.list_recoveries(
            status=status_filter,
            limit=limit,
            offset=offset,
        )
        return RecoveryActionListResponse(
            total=total,
            items=[self._to_response(item) for item in items],
        )
