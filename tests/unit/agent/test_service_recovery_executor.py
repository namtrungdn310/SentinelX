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


@pytest.mark.asyncio
async def test_service_recovery_executor_fails_honestly_on_linux_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("platform.system", lambda: "Linux")
    failing_runner = AsyncMock(return_value=(-1, "", "Cannot execute systemctl: FileNotFoundError"))
    executor = ServiceRecoveryExecutor(command_runner=failing_runner)

    restart_cmd = AgentCommandContract(
        id="c4444444-4444-4444-4444-444444444444",
        action_type=PolicyActionType.RESTART_SERVICE.value,
        target_ip=None,
        command_payload={"service_name": "api-service"},
        created_at=datetime.now(UTC),
    )
    restart_result = await executor.execute(restart_cmd)
    assert restart_result.success is False
    assert "Failed to restart service" in (restart_result.error_message or "")

    cache_runner = AsyncMock(return_value=(1, "", "Permission denied"))
    cache_executor = ServiceRecoveryExecutor(command_runner=cache_runner)
    cache_cmd = AgentCommandContract(
        id="c5555555-5555-5555-5555-555555555555",
        action_type=PolicyActionType.CLEAR_OS_CACHE.value,
        target_ip=None,
        command_payload={},
        created_at=datetime.now(UTC),
    )
    cache_result = await cache_executor.execute(cache_cmd)
    assert cache_result.success is False
    assert "Failed to clear OS cache" in (cache_result.error_message or "")


def test_adaptive_action_validation_accepts_non_ip_target_and_blocks_protected() -> None:
    from sentinelx_agent.defense.validator import LocalSafetyValidator
    from sentinelx_common.contracts.command_parameters import normalize_command

    target, payload = normalize_command("ADAPTIVE", None, {})
    assert target == "adaptive"
    assert payload == {}

    validator = LocalSafetyValidator()
    cmd = AgentCommandContract(
        id="c6666666-6666-6666-6666-666666666666",
        action_type=PolicyActionType.ADAPTIVE.value,
        target_ip=None,
        command_payload={},
        created_at=datetime.now(UTC),
    )
    valid, reason = validator.validate(cmd, "http://127.0.0.1:8000")
    assert valid is True
    assert reason is None

    unsafe_cmd = AgentCommandContract(
        id="c7777777-7777-7777-7777-777777777777",
        action_type=PolicyActionType.ADAPTIVE.value,
        target_ip=None,
        command_payload={"service_name": "sshd"},
        created_at=datetime.now(UTC),
    )
    valid_unsafe, unsafe_reason = validator.validate(unsafe_cmd, "http://127.0.0.1:8000")
    assert valid_unsafe is False
    assert "protected system service" in (unsafe_reason or "")
