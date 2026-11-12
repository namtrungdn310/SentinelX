"""Unit tests for DefenseService."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from sentinelx_common.contracts.defense import (
    CommandAckRequest,
    DefenseActionStatus,
    ManualDefenseActionCreateRequest,
)
from sentinelx_common.contracts.policy import PolicyActionType
from sentinelx_controller.modules.defense.models import DefenseActionModel
from sentinelx_controller.modules.defense.repository import DefenseRepository
from sentinelx_controller.modules.defense.service import DefenseService
from sentinelx_controller.modules.incidents.repository import IncidentRepository


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock(spec=DefenseRepository)
    return repo


@pytest.fixture
def mock_incident_repo() -> AsyncMock:
    return AsyncMock(spec=IncidentRepository)


@pytest.fixture
def defense_service(mock_repo: AsyncMock, mock_incident_repo: AsyncMock) -> DefenseService:
    return DefenseService(
        defense_repo=mock_repo,
        realtime_hub=None,
        publisher=None,
        incident_repo=mock_incident_repo,
    )


@pytest.mark.asyncio
async def test_create_action_from_policy_success(
    defense_service: DefenseService,
    mock_repo: AsyncMock,
) -> None:
    node_id = uuid.uuid4()
    policy_id = uuid.uuid4()
    incident_id = uuid.uuid4()

    mock_repo.has_active_action.return_value = False

    async def fake_create(action: DefenseActionModel) -> DefenseActionModel:
        return action

    mock_repo.create_action.side_effect = fake_create

    resp = await defense_service.create_action_from_policy(
        node_id=node_id,
        action_type=PolicyActionType.BLOCK_IP_NFTABLES.value,
        target_ip="198.51.100.5",
        command_payload={"target": "198.51.100.5", "duration_seconds": 1800},
        incident_id=incident_id,
        policy_id=policy_id,
    )

    assert resp is not None
    assert resp.node_id == str(node_id)
    assert resp.action_type == PolicyActionType.BLOCK_IP_NFTABLES.value
    assert resp.target_ip == "198.51.100.5"
    assert resp.status == DefenseActionStatus.PENDING
    mock_repo.create_action.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_action_from_policy_duplicate_suppressed(
    defense_service: DefenseService,
    mock_repo: AsyncMock,
) -> None:
    node_id = uuid.uuid4()
    mock_repo.has_active_action.return_value = True

    resp = await defense_service.create_action_from_policy(
        node_id=node_id,
        action_type=PolicyActionType.BLOCK_IP_NFTABLES.value,
        target_ip="198.51.100.5",
    )

    assert resp is None
    mock_repo.create_action.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_manual_action(
    defense_service: DefenseService,
    mock_repo: AsyncMock,
) -> None:
    node_id = uuid.uuid4()
    req = ManualDefenseActionCreateRequest(
        node_id=str(node_id),
        action_type=PolicyActionType.RESTART_SERVICE,
        command_payload={"service_name": "nginx"},
    )

    async def fake_create(action: DefenseActionModel) -> DefenseActionModel:
        return action

    mock_repo.create_action.side_effect = fake_create

    resp = await defense_service.create_manual_action(req)
    assert resp.node_id == str(node_id)
    assert resp.action_type == PolicyActionType.RESTART_SERVICE.value
    assert resp.command_payload == {"service_name": "nginx"}
    assert resp.status == DefenseActionStatus.PENDING


@pytest.mark.asyncio
async def test_get_pending_commands_for_node(
    defense_service: DefenseService,
    mock_repo: AsyncMock,
) -> None:
    node_id = uuid.uuid4()
    action = DefenseActionModel(
        id=uuid.uuid4(),
        node_id=node_id,
        action_type="BLOCK_IP_NFTABLES",
        target_ip="203.0.113.10",
        command_payload={},
        status="SENT",
        created_at=datetime.now(UTC),
    )
    mock_repo.get_and_mark_pending_commands.return_value = [action]

    commands = await defense_service.get_pending_commands_for_node(node_id)
    assert len(commands) == 1
    assert commands[0].id == str(action.id)
    assert commands[0].action_type == "BLOCK_IP_NFTABLES"
    assert commands[0].target_ip == "203.0.113.10"


@pytest.mark.asyncio
async def test_record_ack_success(
    defense_service: DefenseService,
    mock_repo: AsyncMock,
) -> None:
    action_id = uuid.uuid4()
    node_id = uuid.uuid4()
    action = DefenseActionModel(
        id=action_id,
        node_id=node_id,
        action_type="BLOCK_IP_NFTABLES",
        target_ip="203.0.113.10",
        command_payload={},
        status="SENT",
        created_at=datetime.now(UTC),
    )
    mock_repo.get_by_id.return_value = action

    async def fake_record(
        action: DefenseActionModel,
        status: str,
        agent_ack_at: datetime,
        error_message: str | None = None,
    ) -> DefenseActionModel:
        action.status = status
        action.agent_ack_at = agent_ack_at
        action.error_message = error_message
        return action

    mock_repo.record_ack.side_effect = fake_record

    ack_req = CommandAckRequest(
        action_id=str(action_id),
        status=DefenseActionStatus.APPLIED,
        execution_metadata={"rule_id": 42},
    )

    ack_resp = await defense_service.record_ack(str(action_id), ack_req)
    assert ack_resp.status == "ok"
    assert ack_resp.action_id == str(action_id)
    assert action.status == "APPLIED"


@pytest.mark.asyncio
async def test_record_ack_not_found(
    defense_service: DefenseService,
    mock_repo: AsyncMock,
) -> None:
    mock_repo.get_by_id.return_value = None
    ack_req = CommandAckRequest(
        action_id=str(uuid.uuid4()),
        status=DefenseActionStatus.APPLIED,
    )
    with pytest.raises(HTTPException) as exc_info:
        await defense_service.record_ack(str(uuid.uuid4()), ack_req)
    assert exc_info.value.status_code == 404
