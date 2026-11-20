"""Unit tests for ServiceRecoveryExecutor."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from sentinelx_agent.defense.executors.recovery import ServiceRecoveryExecutor
from sentinelx_common.contracts.defense import AgentCommandContract
from sentinelx_common.contracts.policy import PolicyActionType


@pytest.mark.asyncio
async def test_service_recovery_executor_restarts_service() -> None:
    mock_runner = AsyncMock(return_value=(0, "restarted", ""))
    executor = ServiceRecoveryExecutor(command_runner=mock_runner)

    cmd = AgentCommandContract(
        id="c1111111-1111-1111-1111-111111111111",
        action_type=PolicyActionType.RESTART_SERVICE.value,
        target_ip=None,
        command_payload={"service_name": "backend-worker"},
        created_at=datetime.now(UTC),
    )

    result = await executor.execute(cmd)
    assert result.success is True
    assert result.metadata.get("executor") == "service_recovery"
    assert result.metadata.get("action") == "restart_service"
    assert result.metadata.get("service_name") == "backend-worker"


@pytest.mark.asyncio
async def test_service_recovery_executor_rejects_empty_service_name() -> None:
    executor = ServiceRecoveryExecutor()

    cmd = AgentCommandContract(
        id="c2222222-2222-2222-2222-222222222222",
        action_type=PolicyActionType.RESTART_SERVICE.value,
        target_ip=None,
        command_payload={},
        created_at=datetime.now(UTC),
    )

    result = await executor.execute(cmd)
    assert result.success is False
    assert "Service name is required" in (result.error_message or "")


@pytest.mark.asyncio
async def test_service_recovery_executor_clears_os_cache() -> None:
    mock_runner = AsyncMock(return_value=(0, "", ""))
    executor = ServiceRecoveryExecutor(command_runner=mock_runner)

    cmd = AgentCommandContract(
        id="c3333333-3333-3333-3333-333333333333",
        action_type=PolicyActionType.CLEAR_OS_CACHE.value,
        target_ip=None,
        command_payload={},
        created_at=datetime.now(UTC),
    )

    result = await executor.execute(cmd)
    assert result.success is True
    assert result.metadata.get("executor") == "service_recovery"
    assert result.metadata.get("action") == "clear_os_cache"
