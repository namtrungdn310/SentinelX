"""Unit tests for Agent LocalSafetyValidator."""

import uuid
from datetime import UTC, datetime

import pytest

from sentinelx_agent.defense.validator import LocalSafetyValidator
from sentinelx_common.contracts.defense import AgentCommandContract
from sentinelx_common.contracts.policy import PolicyActionType


@pytest.fixture
def validator() -> LocalSafetyValidator:
    return LocalSafetyValidator(protected_cidrs=["10.50.0.0/16"])


def make_command(
    action_type: str = PolicyActionType.BLOCK_IP_NFTABLES.value,
    target_ip: str | None = "203.0.113.195",
) -> AgentCommandContract:
    return AgentCommandContract(
        id=str(uuid.uuid4()),
        action_type=action_type,
        target_ip=target_ip,
        command_payload={},
        created_at=datetime.now(UTC),
    )


def test_validator_rejects_loopback(validator: LocalSafetyValidator) -> None:
    cmd_v4 = make_command(target_ip="127.0.0.1")
    is_valid, reason = validator.validate(cmd_v4, controller_url="http://192.168.1.100:8000")
    assert not is_valid
    assert "loopback" in str(reason).lower()

    cmd_v6 = make_command(target_ip="::1")
    is_valid6, reason6 = validator.validate(cmd_v6, controller_url="http://192.168.1.100:8000")
    assert not is_valid6
    assert "loopback" in str(reason6).lower()


def test_validator_rejects_controller_ip_and_host(validator: LocalSafetyValidator) -> None:
    cmd = make_command(target_ip="192.168.1.100")
    is_valid, reason = validator.validate(cmd, controller_url="http://192.168.1.100:8000")
    assert not is_valid
    assert "controller" in str(reason).lower()


def test_validator_rejects_protected_cidr(validator: LocalSafetyValidator) -> None:
    cmd = make_command(target_ip="10.50.12.34")
    is_valid, reason = validator.validate(cmd, controller_url="http://192.168.1.100:8000")
    assert not is_valid
    assert "protected network" in str(reason).lower()


def test_validator_rejects_invalid_action_type(validator: LocalSafetyValidator) -> None:
    cmd = make_command(action_type="UNAUTHORIZED_ROOT_EXEC", target_ip="203.0.113.50")
    is_valid, reason = validator.validate(cmd, controller_url="http://192.168.1.100:8000")
    assert not is_valid
    assert "not supported" in str(reason).lower()


def test_validator_accepts_valid_external_target(validator: LocalSafetyValidator) -> None:
    cmd = make_command(target_ip="198.51.100.99")
    is_valid, reason = validator.validate(cmd, controller_url="http://192.168.1.100:8000")
    assert is_valid
    assert reason is None


def test_validator_accepts_host_level_action_without_ip(validator: LocalSafetyValidator) -> None:
    cmd = make_command(action_type=PolicyActionType.CLEAR_OS_CACHE.value, target_ip=None)
    is_valid, reason = validator.validate(cmd, controller_url="http://192.168.1.100:8000")
    assert is_valid
    assert reason is None
