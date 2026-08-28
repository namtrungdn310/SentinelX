"""Unit tests for YAML configuration loader."""

from pathlib import Path

import pytest

from sentinelx_common.config.yaml_loader import ConfigLoadError, load_yaml_config


def test_load_yaml_valid(tmp_path: Path) -> None:
    """Test loading a valid YAML dictionary."""
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text("environment: test\nserver:\n  port: 9000\n", encoding="utf-8")

    data = load_yaml_config(yaml_file)
    assert data["environment"] == "test"
    assert data["server"]["port"] == 9000


def test_load_yaml_empty(tmp_path: Path) -> None:
    """Test loading an empty YAML file returns an empty dictionary."""
    yaml_file = tmp_path / "empty.yaml"
    yaml_file.write_text("", encoding="utf-8")

    data = load_yaml_config(yaml_file)
    assert data == {}


def test_load_yaml_nonexistent() -> None:
    """Test that loading a non-existent file raises ConfigLoadError."""
    with pytest.raises(ConfigLoadError, match="Configuration file not found"):
        load_yaml_config("nonexistent_file_xyz.yaml")


def test_load_yaml_invalid_syntax(tmp_path: Path) -> None:
    """Test that loading invalid YAML syntax raises ConfigLoadError."""
    yaml_file = tmp_path / "invalid.yaml"
    yaml_file.write_text("key: [unclosed list\n", encoding="utf-8")

    with pytest.raises(ConfigLoadError, match="Failed to parse YAML file"):
        load_yaml_config(yaml_file)


def test_load_yaml_non_dict(tmp_path: Path) -> None:
    """Test that loading a YAML file containing a list instead of a dict raises ConfigLoadError."""
    yaml_file = tmp_path / "list.yaml"
    yaml_file.write_text("- item1\n- item2\n", encoding="utf-8")

    with pytest.raises(ConfigLoadError, match="must be a dictionary"):
        load_yaml_config(yaml_file)
