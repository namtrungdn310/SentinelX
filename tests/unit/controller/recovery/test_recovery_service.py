"""Recovery retry budgets and quiet-observation behavior."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from sentinelx_common.contracts.defense import DefenseActionResponse, DefenseActionStatus
from sentinelx_controller.config import CoreSafetySettings
from sentinelx_controller.modules.recovery.models import RecoveryActionModel
from sentinelx_controller.modules.recovery.service import RecoveryService


def block() -> DefenseActionResponse:
    return DefenseActionResponse(
        id=str(uuid4()),
        node_id=str(uuid4()),
        action_type="BLOCK_IP_NFTABLES",
        status=DefenseActionStatus.APPLIED,
        target_ip="198.51.100.4",
        command_payload={"duration_seconds": 60},
        created_at=datetime.now(UTC) - timedelta(days=1),
        applied_at=datetime.now(UTC),
        effective_until=datetime.now(UTC) + timedelta(seconds=60),
    )


@pytest.mark.asyncio
async def test_creation_age_does_not_expire_a_recently_applied_block() -> None:
    defense, repo = AsyncMock(), AsyncMock()
    defense.applied_actions.return_value = [block()]
    repo.pending.return_value = []
    service = RecoveryService(repo, defense)
    assert await service.scan_and_revert_expired_actions() == []
    defense.queue_unblock.assert_not_awaited()


@pytest.mark.asyncio
async def test_recovery_budget_is_terminal_and_does_not_enqueue_more_work() -> None:
    defense, repo = AsyncMock(), AsyncMock()
    original = block()
    defense.lock_action.return_value = original
    repo.get_by_defense_action_id.return_value = RecoveryActionModel(
        id=uuid4(),
        defense_action_id=uuid4(),
        status="FAILED",
        reason="MANUAL_UNBLOCK",
        executed_at=datetime.now(UTC),
        attempts=3,
    )
    service = RecoveryService(repo, defense)
    with pytest.raises(HTTPException) as error:
        await service.revert_defense_action(original.id)
    assert error.value.status_code == 409
    defense.queue_unblock.assert_not_awaited()


@pytest.mark.asyncio
async def test_unblock_success_does_not_immediately_resolve_incident() -> None:
    defense, repo, incidents = AsyncMock(), AsyncMock(), AsyncMock()
    original = block()
    child = original.model_copy(
        update={
            "id": str(uuid4()),
            "action_type": "UNBLOCK_IP_NFTABLES",
            "command_payload": {"original_defense_action_id": original.id},
        }
    )
    from uuid import UUID

    recovery = RecoveryActionModel(
        id=uuid4(),
        defense_action_id=UUID(original.id),
        command_id=UUID(child.id),
        incident_id=uuid4(),
        status="PENDING",
        reason="MANUAL_UNBLOCK",
        executed_at=datetime.now(UTC),
        attempts=1,
    )
    repo.get_by_defense_action_id.return_value = recovery
    service = RecoveryService(repo, defense, incidents, safety=CoreSafetySettings())
    await service.handle_unblock_ack(child, "APPLIED")
    assert recovery.status == "SUCCESS"
    defense.mark_reverted.assert_awaited_once_with(UUID(original.id))
    incidents.resolve_if_quiet.assert_not_awaited()
