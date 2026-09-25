"""Helper to read YAML config files."""

from pathlib import Path
from typing import Any

import yaml


class ConfigLoadError(Exception):
    """Error raised when the config file cannot be read."""


def load_yaml_config(file_path: str | Path) -> dict[str, Any]:
    """Read and parse a YAML file into a Python dictionary.

    Args:
        file_path: Path to the YAML file.

    Returns:
        Dictionary with config data.

    Raises:
        ConfigLoadError: If file is missing or has bad YAML syntax.
    """
    path = Path(file_path)
    if not path.exists():
        raise ConfigLoadError(f"Configuration file not found: {path}")

    if not path.is_file():
        raise ConfigLoadError(f"Configuration path is not a file: {path}")

    try:
        with open(path, encoding="utf-8") as f:
            content = yaml.safe_load(f)
            if content is None:
                return {}
            if not isinstance(content, dict):
                raise ConfigLoadError(f"YAML content in {path} must be a dictionary/mapping")
            return content
    except yaml.YAMLError as exc:
        raise ConfigLoadError(f"Failed to parse YAML file {path}: {exc}") from exc
    except OSError as exc:
        raise ConfigLoadError(f"Failed to read configuration file {path}: {exc}") from exc
