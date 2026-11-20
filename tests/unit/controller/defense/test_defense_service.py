"""Canonical command safety parameters, independent of database mocks."""

import pytest

from sentinelx_common.contracts.command_parameters import normalize_command


@pytest.mark.parametrize("duration", [0, -1, True, "60", 86401, None])
def test_unsafe_block_durations_are_rejected(duration: object) -> None:
    with pytest.raises(ValueError):
        normalize_command("BLOCK_IP_NFTABLES", "198.51.100.1", {"duration_seconds": duration})


def test_duration_alias_normalizes_without_changing_requested_lifetime() -> None:
    target, payload = normalize_command(
        "BLOCK_IP_NFTABLES",
        "2001:db8:0::1",
        {"block_duration_seconds": 60},
    )
    assert target == "2001:db8::1"
    assert payload == {"duration_seconds": 60}
    with pytest.raises(ValueError, match="Conflicting"):
        normalize_command(
            "BLOCK_IP_NFTABLES",
            target,
            {
                "duration_seconds": 30,
                "block_duration_seconds": 60,
            },
        )


@pytest.mark.parametrize("action", ["RATE_LIMIT", "EJECT_NODE", "KILL_PROCESS"])
def test_unimplemented_actions_never_become_executable_commands(action: str) -> None:
    with pytest.raises(ValueError, match="not supported"):
        normalize_command(action, "198.51.100.1", {})


def test_restart_service_and_clear_cache_are_supported_commands() -> None:
    target, payload = normalize_command("RESTART_SERVICE", None, {"service_name": "backend-worker"})
    assert target == "backend-worker"
    assert payload["service_name"] == "backend-worker"

    cache_target, _ = normalize_command("CLEAR_OS_CACHE", None, {})
    assert cache_target == "os-cache"
