"""Tests for loading Controller settings."""

from pathlib import Path

import pytest

from sentinelx_controller.config import ControllerSettings


def test_default_settings() -> None:
    """Test default values for Controller settings."""
    settings = ControllerSettings()
    assert settings.environment == "development"
    assert settings.service_name == "sentinelx-controller"
    assert settings.server.host == "0.0.0.0"
    assert settings.server.port == 8000
    assert settings.logging.level == "INFO"
    assert settings.logging.json_format is True


def test_load_from_yaml_file(tmp_path: Path) -> None:
    """Test loading settings from a YAML file."""
    yaml_file = tmp_path / "test_controller.yaml"
    yaml_file.write_text(
        """
environment: production
service_name: custom-controller
server:
  host: 127.0.0.1
  port: 8888
logging:
  level: WARNING
  json_format: false
""",
        encoding="utf-8",
    )

    settings = ControllerSettings.load(config_path=yaml_file)
    assert settings.environment == "production"
    assert settings.service_name == "custom-controller"
    assert settings.server.host == "127.0.0.1"
    assert settings.server.port == 8888
    assert settings.logging.level == "WARNING"
    assert settings.logging.json_format is False


def test_env_var_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that environment variables replace YAML and default settings."""
    yaml_file = tmp_path / "test_controller.yaml"
    yaml_file.write_text("environment: staging\nserver:\n  port: 8000\n", encoding="utf-8")

    monkeypatch.setenv("SENTINELX_ENVIRONMENT", "production-override")
    monkeypatch.setenv("SENTINELX_SERVER__PORT", "9999")
    monkeypatch.setenv("SENTINELX_LOGGING__LEVEL", "DEBUG")

    settings = ControllerSettings.load(config_path=yaml_file)
    assert settings.environment == "production-override"
    assert settings.server.port == 9999
    assert settings.logging.level == "DEBUG"
