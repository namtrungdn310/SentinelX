"""Settings and configuration for Controller."""

import ipaddress
import os
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field, field_validator
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


class DatabaseSettings(BaseModel):
    """Settings for PostgreSQL database connection and pool."""

    url: str = Field(
        default="postgresql+asyncpg://sentinelx:sentinelx_password@localhost:5432/sentinelx",
        description="Async SQLAlchemy database connection URL",
    )
    pool_size: int = Field(default=5, ge=1, le=50, description="Connection pool size")
    max_overflow: int = Field(default=10, ge=0, le=50, description="Max overflow connections")
    pool_timeout: float = Field(
        default=30.0, ge=1.0, description="Pool checkout timeout in seconds"
    )
    echo: bool = Field(default=False, description="Log SQL statements")


class DetectionSettings(BaseModel):
    window_size: int = Field(default=10, ge=3, le=100)
    cooldown_seconds: int = Field(default=60, ge=0, le=3600)
    max_gap_seconds: int = Field(default=60, ge=1, le=3600)
    max_sample_age_seconds: int = Field(default=86400, ge=1, le=604800)
    future_skew_seconds: int = Field(default=30, ge=0, le=300)
    network_state_max_entries: int = Field(default=2048, ge=16, le=10000)
    network_state_ttl_seconds: int = Field(default=3600, ge=60, le=86400)


class CoreSafetySettings(BaseModel):
    protected_cidrs: list[str] = Field(default_factory=list)
    command_ttl_seconds: int = Field(default=300, ge=30, le=3600)
    command_lease_seconds: int = Field(default=30, ge=10, le=300)
    command_max_attempts: int = Field(default=5, ge=1, le=20)
    recovery_max_attempts: int = Field(default=3, ge=1, le=10)
    recovery_backoff_seconds: int = Field(default=30, ge=1, le=3600)
    recovery_quiet_seconds: int = Field(default=120, ge=30, le=3600)

    @field_validator("protected_cidrs")
    @classmethod
    def valid_protected_cidrs(cls, value: list[str]) -> list[str]:
        return [str(ipaddress.ip_network(item, strict=False)) for item in value]


class RetentionSettings(BaseModel):
    metric_days: int = Field(default=7, ge=1, le=3650)
    network_days: int = Field(default=3, ge=1, le=3650)
    policy_audit_days: int = Field(default=90, ge=7, le=3650)
    batch_size: int = Field(default=1000, ge=1, le=10000)


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
    safety: CoreSafetySettings = Field(default_factory=CoreSafetySettings)
    retention: RetentionSettings = Field(default_factory=RetentionSettings)

    environment: str = Field(default="development", description="Runtime environment")
    service_name: str = Field(default="sentinelx-controller", description="Service name identifier")
    version: str = Field(default="0.1.0", description="Controller application version")
    lb_admin_token: str | None = Field(
        default=None,
        description="Bearer token sent to sentinelx_lb /lb/admin/* endpoints",
    )
    default_lb_url: str | None = Field(
        default=None,
        description=(
            "Default sentinelx_lb HTTP endpoint used when a project enables LB "
            "without specifying a custom override URL"
        ),
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed CORS origins for Dashboard browser requests",
    )
    agent_bundle_dir: Path = Field(
        default=Path("dist/agent"),
        description="Directory containing built standalone Agent release tarballs",
    )

    server: ServerSettings = Field(default_factory=ServerSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    detection: DetectionSettings = Field(default_factory=DetectionSettings)

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
