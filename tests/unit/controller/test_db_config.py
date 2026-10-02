"""Unit tests for DatabaseSettings and database configuration loading."""

import pytest
from pydantic import ValidationError

from sentinelx_controller.config import ControllerSettings, DatabaseSettings


def test_database_settings_default_values() -> None:
    """Test default values for DatabaseSettings."""
    settings = DatabaseSettings()
    assert "postgresql+asyncpg://" in settings.url
    assert settings.pool_size == 5
    assert settings.max_overflow == 10
    assert settings.pool_timeout == 30.0
    assert settings.echo is False


def test_database_settings_validation_limits() -> None:
    """Test boundary validation for pool size and timeout."""
    with pytest.raises(ValidationError):
        DatabaseSettings(pool_size=0)

    with pytest.raises(ValidationError):
        DatabaseSettings(pool_size=100)

    with pytest.raises(ValidationError):
        DatabaseSettings(pool_timeout=0.5)


def test_controller_settings_includes_database() -> None:
    """Test ControllerSettings includes database settings."""
    settings = ControllerSettings()
    assert isinstance(settings.database, DatabaseSettings)


def test_database_settings_override_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test overriding database settings via environment variables."""
    test_url = "postgresql+asyncpg://custom_user:secret@db.lan:5432/custom_db"
    monkeypatch.setenv("SENTINELX_DATABASE__URL", test_url)
    monkeypatch.setenv("SENTINELX_DATABASE__POOL_SIZE", "8")
    monkeypatch.setenv("SENTINELX_DATABASE__ECHO", "true")

    settings = ControllerSettings.load()
    assert settings.database.url == test_url
    assert settings.database.pool_size == 8
    assert settings.database.echo is True
