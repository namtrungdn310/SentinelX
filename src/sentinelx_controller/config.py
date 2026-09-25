"""Settings and configuration for Controller."""

import os
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class ServerSettings(BaseModel):
    """Settings for HTTP server host and port."""

    host: str = Field(default="0.0.0.0", description="Bind host address")
    port: int = Field(default=8000, ge=1, le=65535, description="Bind port number")


class LoggingSettings(BaseModel):
    """Settings for logging level and format."""

    level: str = Field(default="INFO", description="Log level (DEBUG, INFO, WARNING, ERROR)")
    json_format: bool = Field(default=True, description="Output logs in structured JSON format")


class ControllerSettings(BaseSettings):
    """Main settings for Controller.

    Settings order (higher replaces lower):
    1. Default values
    2. YAML config file
    3. Environment variables (e.g. SENTINELX_SERVER__PORT)
    4. Code arguments
    """

    model_config = SettingsConfigDict(
        env_prefix="SENTINELX_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    _yaml_path: ClassVar[Path | None] = None

    environment: str = Field(default="development", description="Runtime environment")
    service_name: str = Field(default="sentinelx-controller", description="Service name identifier")
    version: str = Field(default="0.1.0", description="Controller application version")

    server: ServerSettings = Field(default_factory=ServerSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Set order of config sources: defaults -> YAML -> environment variables."""
        yaml_file = cls._yaml_path if cls._yaml_path and cls._yaml_path.exists() else None
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls, yaml_file=yaml_file),
            file_secret_settings,
        )

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "ControllerSettings":
        """Load settings from YAML and environment variables.

        Args:
            config_path: Optional path to YAML file.

        Returns:
            ControllerSettings object.
        """
        resolved_path: Path | None = None
        if config_path is not None:
            resolved_path = Path(config_path)
        elif "SENTINELX_CONFIG_FILE" in os.environ:
            resolved_path = Path(os.environ["SENTINELX_CONFIG_FILE"])
        else:
            default_candidate = Path("configs/controller.yaml")
            if default_candidate.exists():
                resolved_path = default_candidate

        cls._yaml_path = resolved_path
        try:
            return cls()
        finally:
            cls._yaml_path = None
