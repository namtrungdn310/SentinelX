"""Unit tests for agent-side recovery validation and execution."""

from datetime import UTC, datetime

import pytest

from sentinelx_agent.defense.executors.simulated import SimulatedDefenseExecutor
from sentinelx_agent.defense.validator import LocalSafetyValidator
from sentinelx_common.contracts.defense import AgentCommandContract
from sentinelx_common.contracts.policy import PolicyActionType


def test_validator_accepts_valid_unblock_command() -> None:
    validator = LocalSafetyValidator()
    cmd = AgentCommandContract(
        id="c1111111-1111-1111-1111-111111111111",
        action_type=PolicyActionType.UNBLOCK_IP_NFTABLES.value,
        target_ip="203.0.113.100",
        command_payload={},
        created_at=datetime.now(UTC),
    )

    is_valid, reason = validator.validate(command=cmd, controller_url="http://127.0.0.1:8000")
    assert is_valid is True
    assert reason is None


def test_validator_rejects_unblock_command_without_target_ip() -> None:
    validator = LocalSafetyValidator()
    cmd = AgentCommandContract(
        id="c2222222-2222-2222-2222-222222222222",
        action_type=PolicyActionType.UNBLOCK_IP_NFTABLES.value,
        target_ip=None,
        command_payload={},
        created_at=datetime.now(UTC),
    )

    is_valid, reason = validator.validate(command=cmd, controller_url="http://127.0.0.1:8000")
    assert is_valid is False
    assert "Target IP is required" in (reason or "")


def test_validator_rejects_unblock_command_with_invalid_ip() -> None:
    validator = LocalSafetyValidator()
    cmd = AgentCommandContract(
        id="c3333333-3333-3333-3333-333333333333",
        action_type=PolicyActionType.UNBLOCK_IP_NFTABLES.value,
        target_ip="999.999.999.999",
        command_payload={},
        created_at=datetime.now(UTC),
    )

    is_valid, reason = validator.validate(command=cmd, controller_url="http://127.0.0.1:8000")
    assert is_valid is False
    assert "Invalid target IP address" in (reason or "")


@pytest.mark.asyncio
async def test_simulated_executor_tracks_block_and_unblock() -> None:
    executor = SimulatedDefenseExecutor()

    block_cmd = AgentCommandContract(
        id="c4444444-4444-4444-4444-444444444444",
        action_type=PolicyActionType.BLOCK_IP_NFTABLES.value,
        target_ip="203.0.113.50",
        command_payload={},
        created_at=datetime.now(UTC),
    )

    block_result = await executor.execute(block_cmd)
    assert block_result.success is True
    assert "203.0.113.50" in executor.blocked_ips
    assert executor.blocked_ips == {"203.0.113.50"}

    unblock_cmd = AgentCommandContract(
        id="c5555555-5555-5555-5555-555555555555",
        action_type=PolicyActionType.UNBLOCK_IP_NFTABLES.value,
        target_ip="203.0.113.50",
        command_payload={},
        created_at=datetime.now(UTC),
    )

    unblock_result = await executor.execute(unblock_cmd)
    assert unblock_result.success is True
    assert "203.0.113.50" not in executor.blocked_ips
    assert len(executor.blocked_ips) == 0
