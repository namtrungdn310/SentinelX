"""Unit tests for Agent CommandProcessor."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from sentinelx_agent.client import ControllerClient
from sentinelx_agent.config import AgentSettings
from sentinelx_agent.defense.executors.base import BaseDefenseExecutor, ExecutionResult
from sentinelx_agent.defense.executors.nftables import NftablesDefenseExecutor
from sentinelx_agent.defense.processor import CommandProcessor
from sentinelx_agent.defense.validator import LocalSafetyValidator
from sentinelx_common.contracts.defense import (
    AgentCommandContract,
    CommandAckResponse,
    DefenseActionStatus,
)


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock(spec=ControllerClient)
    client.ack_defense_action.return_value = CommandAckResponse(
        status="ok",
        action_id=str(uuid.uuid4()),
        acknowledged_at=datetime.now(UTC),
    )
    return client


@pytest.mark.asyncio
async def test_processor_rejects_unsafe_command_and_acks_failed(mock_client: AsyncMock) -> None:
    settings = AgentSettings(controller_url="http://192.168.1.100:8000")
    validator = LocalSafetyValidator()
    executor = AsyncMock(spec=BaseDefenseExecutor)

    processor = CommandProcessor(settings=settings, executor=executor, validator=validator)

    # Command targeting loopback 127.0.0.1
    cmd = AgentCommandContract(
        id=str(uuid.uuid4()),
        action_type="BLOCK_IP_NFTABLES",
        target_ip="127.0.0.1",
        command_payload={},
        created_at=datetime.now(UTC),
    )

    await processor.process_command(cmd, mock_client)

    # Executor must NOT be called
    executor.execute.assert_not_awaited()
    # ACK must be sent with FAILED status
    mock_client.ack_defense_action.assert_awaited_once()
    call_args = mock_client.ack_defense_action.call_args
    ack_req = call_args[0][1]
    assert ack_req.status == DefenseActionStatus.FAILED
    assert "loopback" in ack_req.error_message.lower()


@pytest.mark.asyncio
async def test_processor_executes_valid_command_and_acks_applied(mock_client: AsyncMock) -> None:
    settings = AgentSettings(controller_url="http://192.168.1.100:8000")
    validator = LocalSafetyValidator()
    executor = AsyncMock(spec=BaseDefenseExecutor)
    executor.execute.return_value = ExecutionResult(
        success=True,
        metadata={"simulated": True},
    )

    processor = CommandProcessor(settings=settings, executor=executor, validator=validator)

    cmd = AgentCommandContract(
        id=str(uuid.uuid4()),
        action_type="BLOCK_IP_NFTABLES",
        target_ip="203.0.113.88",
        command_payload={},
        created_at=datetime.now(UTC),
    )

    await processor.process_command(cmd, mock_client)

    executor.execute.assert_awaited_once_with(cmd)
    mock_client.ack_defense_action.assert_awaited_once()
    call_args = mock_client.ack_defense_action.call_args
    ack_req = call_args[0][1]
    assert ack_req.status == DefenseActionStatus.APPLIED
    assert ack_req.error_message is None
    assert ack_req.execution_metadata == {"simulated": True}


@pytest.mark.asyncio
async def test_processor_handles_executor_failure(mock_client: AsyncMock) -> None:
    settings = AgentSettings(controller_url="http://192.168.1.100:8000")
    validator = LocalSafetyValidator()
    executor = AsyncMock(spec=BaseDefenseExecutor)
    executor.execute.return_value = ExecutionResult(
        success=False,
        error_message="nftables command timed out",
    )

    processor = CommandProcessor(settings=settings, executor=executor, validator=validator)

    cmd = AgentCommandContract(
        id=str(uuid.uuid4()),
        action_type="BLOCK_IP_NFTABLES",
        target_ip="203.0.113.88",
        command_payload={},
        created_at=datetime.now(UTC),
    )

    await processor.process_command(cmd, mock_client)

    mock_client.ack_defense_action.assert_awaited_once()
    call_args = mock_client.ack_defense_action.call_args
    ack_req = call_args[0][1]
    assert ack_req.status == DefenseActionStatus.FAILED
    assert "timed out" in ack_req.error_message


def test_processor_instantiates_nftables_executor_from_settings() -> None:
    settings = AgentSettings(defense_executor_type="nftables", nftables_table_name="custom_table")
    processor = CommandProcessor(settings=settings)

    assert isinstance(processor.executor, NftablesDefenseExecutor)
    assert processor.executor.table_name == "custom_table"
