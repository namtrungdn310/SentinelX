"""Unit tests for RecoveryService."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from sentinelx_common.contracts.defense import DefenseActionStatus
from sentinelx_common.contracts.incidents import IncidentStatus
from sentinelx_common.contracts.realtime import RealtimeEventType
from sentinelx_common.contracts.recovery import RecoveryReason, RecoveryStatus
from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub
from sentinelx_controller.modules.defense.models import DefenseActionModel
from sentinelx_controller.modules.defense.repository import DefenseRepository
from sentinelx_controller.modules.incidents.models import IncidentModel
from sentinelx_controller.modules.incidents.repository import IncidentRepository
from sentinelx_controller.modules.recovery.models import RecoveryActionModel
from sentinelx_controller.modules.recovery.repository import RecoveryRepository
from sentinelx_controller.modules.recovery.service import RecoveryService


@pytest.fixture
def mock_recovery_repo() -> AsyncMock:
    return AsyncMock(spec=RecoveryRepository)


@pytest.fixture
def mock_defense_repo() -> AsyncMock:
    return AsyncMock(spec=DefenseRepository)


@pytest.fixture
def mock_incident_repo() -> AsyncMock:
    return AsyncMock(spec=IncidentRepository)


@pytest.fixture
def mock_realtime_hub() -> AsyncMock:
    return AsyncMock(spec=RealtimeHub)


@pytest.fixture
def service(
    mock_recovery_repo: AsyncMock,
    mock_defense_repo: AsyncMock,
    mock_incident_repo: AsyncMock,
    mock_realtime_hub: AsyncMock,
) -> RecoveryService:
    return RecoveryService(
        recovery_repo=mock_recovery_repo,
        defense_repo=mock_defense_repo,
        incident_repo=mock_incident_repo,
        realtime_hub=mock_realtime_hub,
    )


@pytest.mark.asyncio
async def test_revert_defense_action_success(
    service: RecoveryService,
    mock_defense_repo: AsyncMock,
    mock_recovery_repo: AsyncMock,
    mock_realtime_hub: AsyncMock,
) -> None:
    action_id = uuid.uuid4()
    node_id = uuid.uuid4()
    mock_action = DefenseActionModel(
        id=action_id,
        node_id=node_id,
        action_type="BLOCK_IP_NFTABLES",
        target_ip="198.51.100.5",
        status=DefenseActionStatus.APPLIED.value,
        command_payload={"block_duration_seconds": 60},
        created_at=datetime.now(UTC),
    )
    mock_defense_repo.get_by_id.return_value = mock_action
    mock_recovery_repo.get_by_defense_action_id.return_value = None

    result = await service.revert_defense_action(
        defense_action_id_str=str(action_id),
        reason=RecoveryReason.MANUAL_UNBLOCK,
    )

    assert result.defense_action_id == str(action_id)
    assert result.reason == RecoveryReason.MANUAL_UNBLOCK
    assert result.status == RecoveryStatus.PENDING

    mock_recovery_repo.create_recovery.assert_awaited_once()
    mock_defense_repo.create_action.assert_awaited_once()
    created_unblock_cmd = mock_defense_repo.create_action.call_args[0][0]
    assert created_unblock_cmd.action_type == "UNBLOCK_IP_NFTABLES"
    assert created_unblock_cmd.target_ip == "198.51.100.5"
    assert created_unblock_cmd.node_id == node_id
    assert created_unblock_cmd.command_payload["original_defense_action_id"] == str(action_id)

    mock_realtime_hub.broadcast.assert_awaited_once()
    broadcasted_msg = mock_realtime_hub.broadcast.call_args[0][0]
    assert broadcasted_msg.event == RealtimeEventType.DEFENSE_ACTION_CREATED.value


@pytest.mark.asyncio
async def test_revert_defense_action_not_found_raises_404(
    service: RecoveryService,
    mock_defense_repo: AsyncMock,
) -> None:
    action_id = uuid.uuid4()
    mock_defense_repo.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await service.revert_defense_action(str(action_id))
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_revert_defense_action_invalid_uuid_raises_422(
    service: RecoveryService,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await service.revert_defense_action("not-a-valid-uuid")
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_revert_defense_action_idempotent_when_already_reverted(
    service: RecoveryService,
    mock_defense_repo: AsyncMock,
    mock_recovery_repo: AsyncMock,
) -> None:
    action_id = uuid.uuid4()
    mock_action = DefenseActionModel(
        id=action_id,
        node_id=uuid.uuid4(),
        action_type="BLOCK_IP_NFTABLES",
        target_ip="198.51.100.5",
        status=DefenseActionStatus.REVERTED.value,
        command_payload={},
        created_at=datetime.now(UTC),
    )
    mock_defense_repo.get_by_id.return_value = mock_action

    existing_recovery = RecoveryActionModel(
        id=uuid.uuid4(),
        defense_action_id=action_id,
        reason=RecoveryReason.MANUAL_UNBLOCK.value,
        status=RecoveryStatus.SUCCESS.value,
        executed_at=datetime.now(UTC),
    )
    mock_recovery_repo.get_by_defense_action_id.return_value = existing_recovery

    result = await service.revert_defense_action(str(action_id))
    assert result.id == str(existing_recovery.id)
    assert result.status == RecoveryStatus.SUCCESS
    mock_recovery_repo.create_recovery.assert_not_called()


@pytest.mark.asyncio
async def test_scan_and_revert_expired_actions(
    service: RecoveryService,
    mock_defense_repo: AsyncMock,
    mock_recovery_repo: AsyncMock,
) -> None:
    expired_action_id = uuid.uuid4()
    active_action_id = uuid.uuid4()
    node_id = uuid.uuid4()

    now = datetime.now(UTC)

    expired_action = DefenseActionModel(
        id=expired_action_id,
        node_id=node_id,
        action_type="BLOCK_IP_NFTABLES",
        target_ip="198.51.100.10",
        status=DefenseActionStatus.APPLIED.value,
        command_payload={"block_duration_seconds": 60},
        created_at=now - timedelta(seconds=120),
    )

    not_expired_action = DefenseActionModel(
        id=active_action_id,
        node_id=node_id,
        action_type="BLOCK_IP_NFTABLES",
        target_ip="198.51.100.20",
        status=DefenseActionStatus.APPLIED.value,
        command_payload={"block_duration_seconds": 300},
        created_at=now - timedelta(seconds=30),
    )

    mock_defense_repo.get_applied_blocking_actions.return_value = [
        expired_action,
        not_expired_action,
    ]
    mock_recovery_repo.get_by_defense_action_id.return_value = None
    mock_defense_repo.get_by_id.return_value = expired_action

    reverted_list = await service.scan_and_revert_expired_actions(node_id=node_id)

    assert len(reverted_list) == 1
    assert reverted_list[0].defense_action_id == str(expired_action_id)
    assert reverted_list[0].reason == RecoveryReason.TIMEOUT_EXPIRED


@pytest.mark.asyncio
async def test_handle_unblock_ack_success_and_resolves_incident(
    service: RecoveryService,
    mock_defense_repo: AsyncMock,
    mock_recovery_repo: AsyncMock,
    mock_incident_repo: AsyncMock,
    mock_realtime_hub: AsyncMock,
) -> None:
    orig_action_id = uuid.uuid4()
    incident_id = uuid.uuid4()
    node_id = uuid.uuid4()

    orig_action = DefenseActionModel(
        id=orig_action_id,
        node_id=node_id,
        incident_id=incident_id,
        action_type="BLOCK_IP_NFTABLES",
        target_ip="198.51.100.30",
        status=DefenseActionStatus.APPLIED.value,
        command_payload={},
        created_at=datetime.now(UTC),
    )

    unblock_action = DefenseActionModel(
        id=uuid.uuid4(),
        node_id=node_id,
        action_type="UNBLOCK_IP_NFTABLES",
        target_ip="198.51.100.30",
        status=DefenseActionStatus.APPLIED.value,
        command_payload={"original_defense_action_id": str(orig_action_id)},
        created_at=datetime.now(UTC),
    )

    recovery_record = RecoveryActionModel(
        id=uuid.uuid4(),
        defense_action_id=orig_action_id,
        reason=RecoveryReason.TIMEOUT_EXPIRED.value,
        status=RecoveryStatus.PENDING.value,
        executed_at=datetime.now(UTC),
    )

    incident = IncidentModel(
        id=incident_id,
        project_id=uuid.uuid4(),
        title="DDoS Attack",
        status=IncidentStatus.MITIGATING.value,
        severity="HIGH",
        started_at=datetime.now(UTC),
    )

    mock_defense_repo.get_by_id.return_value = orig_action
    mock_recovery_repo.get_by_defense_action_id.return_value = recovery_record
    mock_defense_repo.has_active_blocking_actions_for_incident.return_value = False
    mock_incident_repo.get_by_id.return_value = incident

    await service.handle_unblock_ack(
        unblock_action=unblock_action,
        status_val=DefenseActionStatus.APPLIED.value,
    )

    assert recovery_record.status == RecoveryStatus.SUCCESS.value
    mock_recovery_repo.save.assert_awaited_once_with(recovery_record)
    assert orig_action.status == DefenseActionStatus.REVERTED.value
    assert incident.status == IncidentStatus.RESOLVED.value
    assert incident.resolved_at is not None
    mock_incident_repo.save.assert_awaited_once_with(incident)


@pytest.mark.asyncio
async def test_get_and_list_recoveries(
    service: RecoveryService,
    mock_recovery_repo: AsyncMock,
) -> None:
    rec_id = uuid.uuid4()
    mock_rec = RecoveryActionModel(
        id=rec_id,
        defense_action_id=uuid.uuid4(),
        reason=RecoveryReason.MANUAL_UNBLOCK.value,
        status=RecoveryStatus.SUCCESS.value,
        executed_at=datetime.now(UTC),
    )
    mock_recovery_repo.get_by_id.return_value = mock_rec
    mock_recovery_repo.list_recoveries.return_value = (1, [mock_rec])

    res = await service.get_recovery(str(rec_id))
    assert res.id == str(rec_id)
    assert res.status == RecoveryStatus.SUCCESS

    list_res = await service.list_recoveries(limit=10, offset=0)
    assert list_res.total == 1
    assert len(list_res.items) == 1
