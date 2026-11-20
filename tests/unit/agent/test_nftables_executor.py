"""Verified nft schema, ownership, absolute expiry and failure isolation."""

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from sentinelx_agent.defense.executors.nftables import (
    NftablesDefenseExecutor,
    _default_command_runner,
)
from sentinelx_common.contracts.defense import AgentCommandContract
from tests.nft_fixture import NftKernelFixture


def command(target: str = "198.51.100.6", **overrides: object) -> AgentCommandContract:
    return AgentCommandContract.model_validate(
        {
            "id": str(uuid4()),
            "action_type": "BLOCK_IP_NFTABLES",
            "target_ip": target,
            "command_payload": {"duration_seconds": 60},
            "created_at": datetime.now(UTC),
            **overrides,
        }
    )


@pytest.mark.asyncio
async def test_block_unblock_ipv4_ipv6_and_idempotent_expiry() -> None:
    kernel = NftKernelFixture()
    executor = NftablesDefenseExecutor(command_runner=kernel)
    for target in ("198.51.100.6", "2001:db8::6"):
        deadline = datetime.now(UTC) + timedelta(seconds=60)
        block = command(
            target,
            command_payload={"duration_seconds": 60, "effective_until": deadline.isoformat()},
        )
        first = await executor.execute(block)
        assert first.success, first.error_message
        original = kernel.elements[target][1]
        await asyncio.sleep(0.01)
        assert (await executor.execute(block)).success
        assert kernel.elements[target][1] <= original + 0.05
        assert kernel.elements[target][0] == block.id
        unblock = command(
            target,
            action_type="UNBLOCK_IP_NFTABLES",
            command_payload={"original_defense_action_id": block.id},
        )
        assert (await executor.execute(unblock)).success
        assert target not in kernel.elements
        assert (await executor.execute(unblock)).success


@pytest.mark.asyncio
async def test_missing_table_is_created_then_verified() -> None:
    kernel = NftKernelFixture()
    kernel.objects = None
    executor = NftablesDefenseExecutor(command_runner=kernel)
    ok, error = await executor.ensure_initialized()
    assert ok, error
    assert any(stdin and stdin.startswith("table inet") for _, stdin in kernel.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("removed", ["chain", "rule", "set"])
async def test_names_without_enforcement_never_count_as_initialized(removed: str) -> None:
    kernel = NftKernelFixture()
    assert kernel.objects is not None
    kernel.objects = [item for item in kernel.objects if removed not in item]
    result = await NftablesDefenseExecutor(command_runner=kernel).execute(command())
    assert not result.success
    assert not kernel.elements
    assert not any(stdin for _, stdin in kernel.calls)


@pytest.mark.asyncio
async def test_old_recovery_cannot_remove_a_new_owner() -> None:
    kernel = NftKernelFixture()
    executor = NftablesDefenseExecutor(command_runner=kernel)
    first = command()
    assert (await executor.execute(first)).success
    conflicting = command()
    assert not (await executor.execute(conflicting)).success
    old_recovery = command(
        action_type="UNBLOCK_IP_NFTABLES",
        command_payload={"original_defense_action_id": str(uuid4())},
    )
    assert not (await executor.execute(old_recovery)).success
    assert kernel.elements[first.target_ip or ""][0] == first.id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "parameters",
    [
        {"duration_seconds": 0},
        {"duration_seconds": -1},
        {"duration_seconds": "bad"},
        {"duration_seconds": 86401},
    ],
)
async def test_invalid_parameters_never_touch_the_kernel(parameters: dict[str, object]) -> None:
    kernel = NftKernelFixture()
    result = await NftablesDefenseExecutor(command_runner=kernel).execute(
        command(command_payload=parameters)
    )
    assert not result.success
    assert kernel.calls == []


@pytest.mark.asyncio
async def test_permission_errors_do_not_fabricate_success() -> None:
    kernel = NftKernelFixture()
    kernel.failure = "Operation not permitted"
    result = await NftablesDefenseExecutor(command_runner=kernel).execute(command())
    assert not result.success and "not permitted" in (result.error_message or "")


@pytest.mark.asyncio
async def test_earlier_accept_cannot_bypass_the_owned_drop_rules() -> None:
    kernel = NftKernelFixture()
    assert kernel.objects is not None
    kernel.objects.insert(0, {"rule": {"chain": "guard", "expr": [{"accept": None}]}})
    outcome = await NftablesDefenseExecutor(command_runner=kernel).execute(command())
    assert not outcome.success and not kernel.elements


@pytest.mark.asyncio
async def test_default_command_runner_handles_missing_binary() -> None:
    code, _, error = await _default_command_runner(["sentinelx_nonexistent_binary"])
    assert code == -1 and "FileNotFoundError" in error


@pytest.mark.asyncio
async def test_default_command_runner_handles_timeout() -> None:
    code, _, error = await _default_command_runner(
        [sys.executable, "-c", "import time; time.sleep(2)"], timeout=0.02
    )
    assert code == -1 and "timed out" in error


def test_configuration_cannot_inject_nft_statements() -> None:
    with pytest.raises(ValueError):
        NftablesDefenseExecutor(table_name="sentinelx; flush ruleset")
