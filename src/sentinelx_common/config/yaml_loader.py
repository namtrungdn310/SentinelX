"""YAML configuration loader utility."""

from pathlib import Path
from typing import Any

import yaml


class ConfigLoadError(Exception):
    """Raised when configuration file cannot be loaded or parsed."""


def load_yaml_config(file_path: str | Path) -> dict[str, Any]:
    """Load and parse a YAML configuration file.

    Args:
        file_path: Path to the YAML file.

    Returns:
        Dictionary containing configuration keys and values.

    Raises:
        ConfigLoadError: If the file does not exist or contains invalid YAML.
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
