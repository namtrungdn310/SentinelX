"""Unit tests for AgentSettings."""

from pathlib import Path

import pytest

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
