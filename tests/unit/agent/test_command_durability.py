"""Faults across process boundaries must not duplicate a completed execution."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from sentinelx_agent.client import ControllerClient
from sentinelx_agent.config import AgentSettings
from sentinelx_agent.defense.executors.base import BaseDefenseExecutor, ExecutionResult
from sentinelx_agent.defense.executors.nftables import NftablesDefenseExecutor
from sentinelx_agent.defense.processor import CommandProcessor
from sentinelx_agent.identity import AgentIdentity
from sentinelx_common.contracts.defense import AgentCommandContract, CommandAckResponse
from tests.nft_fixture import NftKernelFixture


@pytest.mark.asyncio
async def test_lost_ack_and_restart_reuses_receipt_without_execution(tmp_path: Path) -> None:
    settings = AgentSettings(
        controller_url="http://192.0.2.10", command_journal_path=tmp_path / "journal.db"
    )
    executor = AsyncMock(spec=BaseDefenseExecutor)
    executor.execute.return_value = ExecutionResult(success=True, metadata={"executor": "nftables"})
    client = AsyncMock(spec=ControllerClient)
    client.ack_defense_action.side_effect = TimeoutError("lost ACK response")
    command = AgentCommandContract(
        id=str(uuid4()),
        action_type="BLOCK_IP_NFTABLES",
        target_ip="198.51.100.60",
        created_at=datetime.now(UTC),
        command_payload={"duration_seconds": 30},
    )
    first = CommandProcessor(settings, executor=executor)
    assert await first.process_command(command, client) is None
    assert executor.execute.await_count == 1
    before = client.ack_defense_action.call_args.args[1]
    restarted = CommandProcessor(settings, executor=executor)
    client.ack_defense_action.side_effect = None
    client.ack_defense_action.return_value = CommandAckResponse(
        action_id=command.id, acknowledged_at=datetime.now(UTC)
    )
    assert await restarted.process_command(command, client) is not None
    assert executor.execute.await_count == 1
    assert client.ack_defense_action.call_args.args[1] == before
    assert restarted.journal.pending() == []
    changed = command.model_copy(update={"target_ip": "198.51.100.61"})
    assert await restarted.process_command(changed, client) is None
    assert executor.execute.await_count == 1


@pytest.mark.asyncio
async def test_command_execution_does_not_block_the_heartbeat_caller(tmp_path: Path) -> None:
    settings = AgentSettings(command_journal_path=tmp_path / "journal.db")
    entered, release, stop = asyncio.Event(), asyncio.Event(), asyncio.Event()
    executor = AsyncMock(spec=BaseDefenseExecutor)

    async def execute(command: AgentCommandContract) -> ExecutionResult:
        entered.set()
        await release.wait()
        return ExecutionResult(success=True, metadata={"simulated": True})

    executor.execute.side_effect = execute
    client = AsyncMock(spec=ControllerClient)
    client.ack_defense_action.return_value = CommandAckResponse(
        action_id=str(uuid4()), acknowledged_at=datetime.now(UTC)
    )
    processor = CommandProcessor(settings, executor=executor)
    processor.enqueue(
        AgentCommandContract(
            id=str(uuid4()),
            action_type="BLOCK_IP_NFTABLES",
            target_ip="198.51.100.62",
            created_at=datetime.now(UTC),
        )
    )
    task = asyncio.create_task(processor.run(client, stop))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        await asyncio.wait_for(asyncio.sleep(0), 0.1)
        assert not task.done()
    finally:
        release.set()
        stop.set()
        await asyncio.wait_for(task, 2)


@pytest.mark.asyncio
async def test_restart_restores_only_live_owned_blocks_with_original_deadline(
    tmp_path: Path,
) -> None:
    settings = AgentSettings(
        controller_url="http://192.0.2.10",
        command_journal_path=tmp_path / "journal.db",
        defense_executor_type="nftables",
    )
    identity = AgentIdentity(
        node_id=str(uuid4()), agent_id=str(uuid4()), enrolled_at=datetime.now(UTC)
    )
    kernel = NftKernelFixture()
    executor = NftablesDefenseExecutor(command_runner=kernel)
    client = AsyncMock(spec=ControllerClient)
    client.ack_defense_action.return_value = CommandAckResponse(
        action_id=str(uuid4()), acknowledged_at=datetime.now(UTC)
    )
    command = AgentCommandContract(
        id=str(uuid4()),
        node_id=identity.node_id,
        action_type="BLOCK_IP_NFTABLES",
        target_ip="198.51.100.66",
        command_payload={"duration_seconds": 60},
        created_at=datetime.now(UTC),
    )
    processor = CommandProcessor(settings, executor=executor)
    processor.set_identity(identity)
    await processor.process_command(command, client)
    deadline = kernel.elements[command.target_ip or ""][1]
    kernel.elements.clear()  # Simulates loss of this private namespace's kernel rules.
    restarted = CommandProcessor(settings, executor=executor)
    restarted.set_identity(identity)
    await restarted.reconcile_kernel()
    assert kernel.elements[command.target_ip or ""][0] == command.id
    assert kernel.elements[command.target_ip or ""][1] <= deadline + 0.1
    unblock = AgentCommandContract(
        id=str(uuid4()),
        node_id=identity.node_id,
        action_type="UNBLOCK_IP_NFTABLES",
        target_ip=command.target_ip,
        command_payload={"original_defense_action_id": command.id},
        created_at=datetime.now(UTC),
    )
    await restarted.process_command(unblock, client)
    await restarted.reconcile_kernel()
    assert not kernel.elements
