"""Unit tests for NftablesDefenseExecutor."""

import sys
import uuid
from datetime import UTC, datetime

import pytest

from sentinelx_agent.defense.executors.nftables import (
    NftablesDefenseExecutor,
    _default_command_runner,
)
from sentinelx_common.contracts.defense import AgentCommandContract
from sentinelx_common.contracts.policy import PolicyActionType


class MockCommandRunner:
    """Mock runner recording commands and returning configurable responses."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], str | None]] = []
        self.responses: dict[str, tuple[int, str, str]] = {}
        self.default_response: tuple[int, str, str] = (0, "", "")

    def set_response(self, prefix: str, exit_code: int, stdout: str = "", stderr: str = "") -> None:
        self.responses[prefix] = (exit_code, stdout, stderr)

    async def __call__(self, cmd: list[str], stdin: str | None) -> tuple[int, str, str]:
        self.calls.append((cmd, stdin))
        cmd_str = " ".join(cmd)
        for prefix, resp in self.responses.items():
            if prefix in cmd_str:
                return resp
        return self.default_response


@pytest.fixture
def mock_runner() -> MockCommandRunner:
    runner = MockCommandRunner()
    # Default list table succeeds and has sets
    runner.set_response(
        "list table",
        0,
        stdout="table inet sentinelx {\n  set blocked_v4 {}\n  set blocked_v6 {}\n}",
    )
    return runner


def test_build_init_script() -> None:
    executor = NftablesDefenseExecutor(table_name="sentinelx_test")
    script = executor.build_init_script()

    assert "table inet sentinelx_test" in script
    assert "set blocked_v4" in script
    assert "set blocked_v6" in script
    assert "flags timeout" in script
    assert "chain input" in script
    assert "type filter hook input priority -100" in script
    assert "ip saddr @blocked_v4 drop" in script
    assert "ip6 saddr @blocked_v6 drop" in script


@pytest.mark.asyncio
async def test_ensure_initialized_already_exists(mock_runner: MockCommandRunner) -> None:
    executor = NftablesDefenseExecutor(
        table_name="sentinelx",
        command_runner=mock_runner,
    )
    ok, err = await executor.ensure_initialized()

    assert ok is True
    assert err is None
    # Checked once, did not apply script
    assert len(mock_runner.calls) == 1
    assert mock_runner.calls[0][0] == ["nft", "list", "table", "inet", "sentinelx"]


@pytest.mark.asyncio
async def test_ensure_initialized_creates_table_when_missing(
    mock_runner: MockCommandRunner,
) -> None:
    mock_runner.set_response("list table", 1, stderr="No such file or directory")
    mock_runner.set_response("-f -", 0, stdout="")

    executor = NftablesDefenseExecutor(
        table_name="sentinelx",
        command_runner=mock_runner,
    )
    ok, err = await executor.ensure_initialized()

    assert ok is True
    assert err is None
    assert len(mock_runner.calls) == 2
    assert mock_runner.calls[0][0] == ["nft", "list", "table", "inet", "sentinelx"]
    assert mock_runner.calls[1][0] == ["nft", "-f", "-"]
    assert "table inet sentinelx" in (mock_runner.calls[1][1] or "")


@pytest.mark.asyncio
async def test_ensure_initialized_fails_on_permission_denied(
    mock_runner: MockCommandRunner,
) -> None:
    mock_runner.set_response("list table", 1, stderr="No such table")
    mock_runner.set_response("-f -", 1, stderr="Operation not permitted")

    executor = NftablesDefenseExecutor(
        table_name="sentinelx",
        command_runner=mock_runner,
    )
    ok, err = await executor.ensure_initialized()

    assert ok is False
    assert err is not None
    assert "Operation not permitted" in err


@pytest.mark.asyncio
async def test_block_ipv4_with_timeout(mock_runner: MockCommandRunner) -> None:
    executor = NftablesDefenseExecutor(command_runner=mock_runner)
    cmd = AgentCommandContract(
        id=str(uuid.uuid4()),
        action_type=PolicyActionType.BLOCK_IP_NFTABLES.value,
        target_ip="203.0.113.195",
        command_payload={"duration_seconds": 900},
        created_at=datetime.now(UTC),
    )

    result = await executor.execute(cmd)

    assert result.success is True
    assert result.metadata["target_ip"] == "203.0.113.195"
    assert result.metadata["set"] == "blocked_v4"
    assert result.metadata["duration_seconds"] == 900

    last_call = mock_runner.calls[-1]
    assert last_call[0] == [
        "nft",
        "add",
        "element",
        "inet",
        "sentinelx",
        "blocked_v4",
        "{ 203.0.113.195 timeout 900s }",
    ]


@pytest.mark.asyncio
async def test_block_ipv6_with_timeout(mock_runner: MockCommandRunner) -> None:
    executor = NftablesDefenseExecutor(command_runner=mock_runner)
    cmd = AgentCommandContract(
        id=str(uuid.uuid4()),
        action_type=PolicyActionType.BLOCK_IP_NFTABLES.value,
        target_ip="2001:db8::99",
        command_payload={"duration_seconds": 600},
        created_at=datetime.now(UTC),
    )

    result = await executor.execute(cmd)

    assert result.success is True
    assert result.metadata["target_ip"] == "2001:db8::99"
    assert result.metadata["set"] == "blocked_v6"
    assert result.metadata["duration_seconds"] == 600

    last_call = mock_runner.calls[-1]
    assert last_call[0] == [
        "nft",
        "add",
        "element",
        "inet",
        "sentinelx",
        "blocked_v6",
        "{ 2001:db8::99 timeout 600s }",
    ]


@pytest.mark.asyncio
async def test_block_ipv4_default_timeout_fallback(mock_runner: MockCommandRunner) -> None:
    executor = NftablesDefenseExecutor(command_runner=mock_runner)
    cmd = AgentCommandContract(
        id=str(uuid.uuid4()),
        action_type=PolicyActionType.BLOCK_IP_NFTABLES.value,
        target_ip="198.51.100.22",
        command_payload={},
        created_at=datetime.now(UTC),
    )

    result = await executor.execute(cmd)

    assert result.success is True
    assert result.metadata["duration_seconds"] == 1800
    last_call = mock_runner.calls[-1]
    assert "timeout 1800s" in last_call[0][-1]


@pytest.mark.asyncio
async def test_block_ipv4_zero_timeout_indefinite(mock_runner: MockCommandRunner) -> None:
    executor = NftablesDefenseExecutor(command_runner=mock_runner)
    cmd = AgentCommandContract(
        id=str(uuid.uuid4()),
        action_type=PolicyActionType.BLOCK_IP_NFTABLES.value,
        target_ip="198.51.100.33",
        command_payload={"duration_seconds": 0},
        created_at=datetime.now(UTC),
    )

    result = await executor.execute(cmd)

    assert result.success is True
    last_call = mock_runner.calls[-1]
    assert last_call[0][-1] == "{ 198.51.100.33 }"


@pytest.mark.asyncio
async def test_unblock_ipv4_success(mock_runner: MockCommandRunner) -> None:
    executor = NftablesDefenseExecutor(command_runner=mock_runner)
    cmd = AgentCommandContract(
        id=str(uuid.uuid4()),
        action_type=PolicyActionType.UNBLOCK_IP_NFTABLES.value,
        target_ip="203.0.113.195",
        command_payload={},
        created_at=datetime.now(UTC),
    )

    result = await executor.execute(cmd)

    assert result.success is True
    assert result.metadata["action"] == "UNBLOCK_IP_NFTABLES"
    last_call = mock_runner.calls[-1]
    assert last_call[0] == [
        "nft",
        "delete",
        "element",
        "inet",
        "sentinelx",
        "blocked_v4",
        "{ 203.0.113.195 }",
    ]


@pytest.mark.asyncio
async def test_unblock_handles_already_expired_element(mock_runner: MockCommandRunner) -> None:
    mock_runner.set_response(
        "delete element",
        1,
        stderr="Error: No such file or directory; element does not exist",
    )
    executor = NftablesDefenseExecutor(command_runner=mock_runner)
    cmd = AgentCommandContract(
        id=str(uuid.uuid4()),
        action_type=PolicyActionType.UNBLOCK_IP_NFTABLES.value,
        target_ip="203.0.113.195",
        command_payload={},
        created_at=datetime.now(UTC),
    )

    result = await executor.execute(cmd)

    assert result.success is True
    assert result.metadata.get("status") == "already_removed"


@pytest.mark.asyncio
async def test_unsupported_action_type(mock_runner: MockCommandRunner) -> None:
    executor = NftablesDefenseExecutor(command_runner=mock_runner)
    cmd = AgentCommandContract(
        id=str(uuid.uuid4()),
        action_type="RESTART_SERVICE",
        target_ip="203.0.113.195",
        command_payload={},
        created_at=datetime.now(UTC),
    )

    result = await executor.execute(cmd)

    assert result.success is False
    assert "not supported" in (result.error_message or "")


@pytest.mark.asyncio
async def test_missing_target_ip(mock_runner: MockCommandRunner) -> None:
    executor = NftablesDefenseExecutor(command_runner=mock_runner)
    cmd = AgentCommandContract(
        id=str(uuid.uuid4()),
        action_type="BLOCK_IP_NFTABLES",
        target_ip=None,
        command_payload={},
        created_at=datetime.now(UTC),
    )

    result = await executor.execute(cmd)

    assert result.success is False
    assert "Target IP is required" in (result.error_message or "")


@pytest.mark.asyncio
async def test_invalid_target_ip(mock_runner: MockCommandRunner) -> None:
    executor = NftablesDefenseExecutor(command_runner=mock_runner)
    cmd = AgentCommandContract(
        id=str(uuid.uuid4()),
        action_type="BLOCK_IP_NFTABLES",
        target_ip="not_an_ip_addr",
        command_payload={},
        created_at=datetime.now(UTC),
    )

    result = await executor.execute(cmd)

    assert result.success is False
    assert "Invalid target IP address" in (result.error_message or "")


@pytest.mark.asyncio
async def test_nft_command_failure_reports_error(mock_runner: MockCommandRunner) -> None:
    mock_runner.set_response(
        "add element",
        1,
        stderr="Error: Could not process rule: Permission denied",
    )
    executor = NftablesDefenseExecutor(command_runner=mock_runner)
    cmd = AgentCommandContract(
        id=str(uuid.uuid4()),
        action_type="BLOCK_IP_NFTABLES",
        target_ip="203.0.113.195",
        command_payload={},
        created_at=datetime.now(UTC),
    )

    result = await executor.execute(cmd)

    assert result.success is False
    assert "Permission denied" in (result.error_message or "")
    assert result.metadata.get("exit_code") == 1


@pytest.mark.asyncio
async def test_default_command_runner_handles_missing_binary() -> None:
    code, out, err = await _default_command_runner(["nonexistent_nft_bin_12345"])
    assert code == -1
    assert "not found on system PATH" in err


@pytest.mark.asyncio
async def test_default_command_runner_handles_timeout() -> None:
    # Use python sleep to simulate a hung process
    sleep_cmd = [sys.executable, "-c", "import time; time.sleep(1.0)"]
    code, out, err = await _default_command_runner(sleep_cmd, timeout=0.05)
    assert code == -1
    assert "timed out after" in err
