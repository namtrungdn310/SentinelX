"""Owned unblock retries; execution expiry and observed quiet govern recovery."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException

from sentinelx_common.contracts.defense import DefenseActionResponse
from sentinelx_common.contracts.realtime import RealtimeEventType, RealtimeMessage
from sentinelx_common.contracts.recovery import (
    RecoveryActionListResponse,
    RecoveryActionResponse,
    RecoveryReason,
    RecoveryStatus,
)
from sentinelx_common.utils.time import ensure_utc
from sentinelx_controller.config import CoreSafetySettings
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub
from sentinelx_controller.infrastructure.realtime.publisher import CommittedPublisher
from sentinelx_controller.modules.defense.service import DefenseService
from sentinelx_controller.modules.incidents.service import IncidentService
from sentinelx_controller.modules.recovery.models import RecoveryActionModel
from sentinelx_controller.modules.recovery.repository import RecoveryRepository


class RecoveryService:
    def __init__(
        self,
        recovery_repo: RecoveryRepository,
        defense_service: DefenseService,
        incident_service: IncidentService | None = None,
        realtime_hub: RealtimeHub | None = None,
        publisher: CommittedPublisher | None = None,
        safety: CoreSafetySettings | None = None,
    ) -> None:
        self._repo, self._defense = recovery_repo, defense_service
        self._incidents, self._hub, self._publisher = incident_service, realtime_hub, publisher
        self._safety = safety or CoreSafetySettings()

    def _to_response(self, model: RecoveryActionModel) -> RecoveryActionResponse:
        return RecoveryActionResponse(
            id=str(model.id),
            defense_action_id=str(model.defense_action_id),
            reason=RecoveryReason(model.reason),
            status=RecoveryStatus(model.status),
            executed_at=ensure_utc(model.executed_at),
            attempts=model.attempts or 1,
            next_retry_at=model.next_retry_at,
            error_message=model.error_message,
        )

    async def _broadcast(self, event: RealtimeEventType, recovery: RecoveryActionModel) -> None:
        message = RealtimeMessage(
            event=event.value,
            data=self._to_response(recovery).model_dump(mode="json"),
            timestamp=datetime.now(UTC),
        )
        if self._publisher:
            self._publisher.enqueue(message)
        elif self._hub:
            await self._hub.broadcast(message)

    async def revert_defense_action(
        self,
        defense_action_id_str: str,
        reason: RecoveryReason = RecoveryReason.MANUAL_UNBLOCK,
    ) -> RecoveryActionResponse:
        try:
            action_id = uuid.UUID(defense_action_id_str)
        except ValueError as error:
            raise HTTPException(422, "Invalid defense action UUID") from error
        action = await self._defense.lock_action(action_id)
        if action is None:
            raise HTTPException(404, "Defense action not found")
        existing = await self._repo.get_by_defense_action_id(action_id)
        if existing and existing.status in {"PENDING", "SUCCESS"}:
            return self._to_response(existing)
        if action.action_type != "BLOCK_IP_NFTABLES" or action.status != "APPLIED":
            raise HTTPException(409, "Only an acknowledged real block can be recovered")
        now = datetime.now(UTC)
        if existing:
            if existing.attempts >= self._safety.recovery_max_attempts:
                raise HTTPException(
                    409, "Recovery retry budget exhausted; operator reconciliation required"
                )
            if existing.next_retry_at and ensure_utc(existing.next_retry_at) > now:
                raise HTTPException(409, "Recovery retry backoff is active")
            existing.attempts += 1
            existing.status = "PENDING"
            existing.executed_at = now
            recovery = existing
        else:
            recovery = RecoveryActionModel(
                id=uuid.uuid4(),
                defense_action_id=action_id,
                reason=reason.value,
                status="PENDING",
                executed_at=now,
                attempts=1,
                node_id=uuid.UUID(action.node_id),
                incident_id=uuid.UUID(action.incident_id) if action.incident_id else None,
            )
            await self._repo.create_recovery(recovery)
        child = await self._defense.queue_unblock(action)
        recovery.command_id = uuid.UUID(child.id)
        recovery.next_retry_at = None
        await self._repo.save(recovery)
        return self._to_response(recovery)

    async def _failed(self, recovery: RecoveryActionModel, error: str) -> None:
        recovery.status = "FAILED"
        recovery.error_message = error[:1000]
        recovery.executed_at = datetime.now(UTC)
        recovery.next_retry_at = (
            recovery.executed_at
            + timedelta(
                seconds=self._safety.recovery_backoff_seconds * 2 ** (recovery.attempts - 1),
            )
            if recovery.attempts < self._safety.recovery_max_attempts
            else None
        )
        await self._repo.save(recovery)

    async def scan_and_revert_expired_actions(
        self,
        node_id: uuid.UUID | None = None,
    ) -> list[RecoveryActionResponse]:
        if node_id is None:
            nodes = {
                uuid.UUID(action.node_id) for action in await self._defense.applied_actions(None)
            }
            for recovery in [
                *await self._repo.pending(None),
                *await self._repo.completed_for_resolution(None),
            ]:
                if recovery.node_id is not None:
                    nodes.add(recovery.node_id)
                else:
                    parent = await self._defense.lock_action(recovery.defense_action_id)
                    if parent is not None:
                        recovery.node_id = uuid.UUID(parent.node_id)
                        nodes.add(recovery.node_id)
            results: list[RecoveryActionResponse] = []
            for node in sorted(nodes, key=str):
                results.extend(await self.scan_and_revert_expired_actions(node))
            return results
        await self._defense.lock_node(node_id)
        now = datetime.now(UTC)
        for pending in await self._repo.pending(node_id):
            if pending.command_id is None:
                await self._failed(
                    pending, "Legacy recovery has no tracked command; reconcile manually"
                )
                continue
            child = await self._defense.lock_action(pending.command_id)
            if child and child.status in {"FAILED", "EXPIRED", "CANCELLED", "SIMULATED", "SKIPPED"}:
                await self._failed(pending, child.error_message or "Unblock did not apply")
        results = []
        for action in await self._defense.applied_actions(node_id):
            if action.effective_until is None or ensure_utc(action.effective_until) > now:
                continue
            prior = await self._repo.get_by_defense_action_id(uuid.UUID(action.id))
            if prior and prior.status in {"PENDING", "SUCCESS"}:
                continue
            if prior and (
                prior.attempts >= self._safety.recovery_max_attempts
                or (prior.next_retry_at and ensure_utc(prior.next_retry_at) > now)
            ):
                continue
            results.append(
                await self.revert_defense_action(action.id, RecoveryReason.TIMEOUT_EXPIRED)
            )
        if self._incidents:
            for recovery in await self._repo.completed_for_resolution(node_id):
                if recovery.incident_id is None:
                    recovery.resolution_done = True
                    continue
                if now - ensure_utc(recovery.executed_at) < timedelta(
                    seconds=self._safety.recovery_quiet_seconds
                ):
                    continue
                if await self._defense.has_active_incident_actions(recovery.incident_id):
                    continue
                closed = await self._incidents.resolve_if_quiet(
                    recovery.incident_id,
                    ensure_utc(recovery.executed_at),
                )
                if closed:
                    recovery.resolution_done = True
                    await self._repo.save(recovery)
        return results

    async def handle_unblock_ack(
        self,
        unblock_action: DefenseActionResponse,
        status_val: str,
        error_message: str | None = None,
    ) -> None:
        original = unblock_action.command_payload.get("original_defense_action_id")
        if not isinstance(original, str):
            raise HTTPException(409, "Unblock has no owner")
        recovery = await self._repo.get_by_defense_action_id(uuid.UUID(original))
        if recovery is None or str(recovery.command_id) != unblock_action.id:
            raise HTTPException(409, "ACK belongs to a stale recovery attempt")
        if status_val == "APPLIED":
            await self._defense.mark_reverted(uuid.UUID(original))
            recovery.status = "SUCCESS"
            recovery.executed_at = datetime.now(UTC)
            recovery.error_message, recovery.next_retry_at = None, None
            await self._repo.save(recovery)
            await self._broadcast(RealtimeEventType.RECOVERY_COMPLETED, recovery)
            # Resolution happens only after a later, fresh and quiet observation interval.
        else:
            await self._failed(
                recovery, error_message or "Unblock was not applied by a real executor"
            )

    async def get_recovery(self, recovery_id_str: str) -> RecoveryActionResponse:
        try:
            recovery_id = uuid.UUID(recovery_id_str)
        except ValueError as error:
            raise HTTPException(422, "Invalid recovery UUID") from error
        result = await self._repo.get_by_id(recovery_id)
        if result is None:
            raise HTTPException(404, "Recovery not found")
        return self._to_response(result)

    async def list_recoveries(
        self,
        status_filter: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> RecoveryActionListResponse:
        total, records = await self._repo.list_recoveries(status_filter, limit, offset)
        return RecoveryActionListResponse(
            total=total, items=[self._to_response(r) for r in records]
        )
