"""Unit tests for AgentSettings."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from sentinelx_agent.config import AgentSettings


def test_agent_settings_default_values() -> None:
    """Test AgentSettings default parameters."""
    settings = AgentSettings()
    assert settings.controller_url == "http://localhost:8000"
    assert settings.heartbeat_interval_seconds == 10
    assert settings.agent_version == "0.1.0"
    assert settings.identity_path == Path("data/agent_identity.json")


def test_agent_settings_strips_trailing_slash() -> None:
    """Test controller_url strips any trailing slash."""
    settings = AgentSettings(controller_url="http://192.168.1.50:8000/")
    assert settings.controller_url == "http://192.168.1.50:8000"


@pytest.mark.parametrize(
    "url",
    [
        "ftp://controller",
        "controller:8000",
        "https://user:secret@controller",
        "https://controller?token=secret",
        "http://controller/#secret",
    ],
)
def test_agent_rejects_unsafe_controller_url(url: str) -> None:
    with pytest.raises(ValidationError):
        AgentSettings(controller_url=url)


def test_agent_requires_uuid_and_explicit_config_must_exist(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        AgentSettings(node_id="node-backend01")
    with pytest.raises(ValueError, match="does not exist"):
        AgentSettings.load(tmp_path / "missing.yaml")


def test_enrollment_token_is_not_in_settings_repr() -> None:
    assert "private-secret" not in repr(AgentSettings(enrollment_token="private-secret"))


def test_agent_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test environment variable overrides."""
    monkeypatch.setenv("SENTINELX_CONTROLLER_URL", "http://prod-controller:9000")
    monkeypatch.setenv("SENTINELX_NODE_ID", "11111111-2222-3333-4444-555555555555")
    monkeypatch.setenv("SENTINELX_ENROLLMENT_TOKEN", "my-secret-token")
    monkeypatch.setenv("SENTINELX_HEARTBEAT_INTERVAL", "15")

    settings = AgentSettings.load()
    assert settings.controller_url == "http://prod-controller:9000"
    assert settings.node_id == "11111111-2222-3333-4444-555555555555"
    assert settings.enrollment_token == "my-secret-token"
    assert settings.heartbeat_interval_seconds == 15


def test_agent_settings_rejects_unknown_collector() -> None:
    with pytest.raises(ValidationError, match="telemetry_collector_type"):
        AgentSettings.model_validate({"telemetry_collector_type": "typo"})


def test_collector_yaml_and_environment_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "agent.yaml"
    config.write_text(
        "agent:\n  telemetry_collector_type: fake\n  telemetry_disk_path: /data\n"
        "  telemetry_batch_size: 2\n",
        encoding="utf-8",
    )
    settings = AgentSettings.load(config)
    assert settings.telemetry_collector_type == "fake"
    assert settings.telemetry_disk_path == "/data"
    assert settings.telemetry_batch_size == 2
    monkeypatch.setenv("SENTINELX_TELEMETRY_COLLECTOR_TYPE", "real")
    monkeypatch.setenv("SENTINELX_TELEMETRY_DISK_PATH", "/srv")
    overridden = AgentSettings.load(config)
    assert overridden.telemetry_collector_type == "real"
    assert overridden.telemetry_disk_path == "/srv"
