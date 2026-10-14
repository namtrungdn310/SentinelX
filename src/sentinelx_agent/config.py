"""Configuration settings for SentinelX Agent daemon."""

import os
import platform
import socket
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from sentinelx_common.config.yaml_loader import load_yaml_config


class AgentSettings(BaseSettings):
    """Runtime configuration for SentinelX Agent daemon."""

    model_config = SettingsConfigDict(
        env_prefix="SENTINELX_",
        case_sensitive=False,
        extra="ignore",
    )

    controller_url: str = Field(
        default="http://localhost:8000",
        description="URL of SentinelX Controller API",
    )
    node_id: str | None = Field(
        default=None,
        description="Target node UUID string assigned by Controller",
    )
    enrollment_token: str | None = Field(
        default=None,
        description="One-time secret token for agent enrollment",
    )
    heartbeat_interval_seconds: int = Field(
        default=10,
        ge=1,
        le=3600,
        description="Interval between heartbeats in seconds",
    )
    identity_path: Path = Field(
        default=Path("data/agent_identity.json"),
        description="Path to local identity file storing agent_id",
    )
    hostname: str = Field(
        default_factory=socket.gethostname,
        description="Hostname of the Linux machine",
    )
    agent_version: str = Field(
        default="0.1.0",
        description="Agent daemon software version",
    )
    os_info: str = Field(
        default_factory=lambda: f"{platform.system()} {platform.release()} ({platform.machine()})",
        description="Operating system description",
    )
    timeout_seconds: float = Field(
        default=5.0,
        ge=0.1,
        le=60.0,
        description="HTTP request timeout in seconds",
    )
    retry_initial_delay_seconds: float = Field(
        default=1.0,
        ge=0.1,
        description="Initial delay before retrying failed requests",
    )
    retry_max_delay_seconds: float = Field(
        default=30.0,
        ge=1.0,
        description="Maximum backoff delay for retries",
    )
    retry_backoff_factor: float = Field(
        default=2.0,
        ge=1.0,
        description="Exponential multiplier for retry backoff",
    )

    @field_validator("controller_url")
    @classmethod
    def clean_controller_url(cls, v: str) -> str:
        """Strip trailing slash from Controller URL."""
        return v.rstrip("/")

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "AgentSettings":
        """Load settings from optional YAML file and environment variables."""
        yaml_data: dict[str, Any] = {}
        if config_path is not None:
            path = Path(config_path)
            if path.is_file():
                raw = load_yaml_config(path)
                if isinstance(raw, dict):
                    # Flatten nested yaml format if present
                    controller_section = raw.get("controller", {})
                    agent_section = raw.get("agent", {})
                    if isinstance(controller_section, dict):
                        if "url" in controller_section:
                            yaml_data["controller_url"] = controller_section["url"]
                        if "enrollment_token" in controller_section:
                            yaml_data["enrollment_token"] = controller_section["enrollment_token"]
                        if "timeout_seconds" in controller_section:
                            yaml_data["timeout_seconds"] = controller_section["timeout_seconds"]
                    if isinstance(agent_section, dict):
                        if "node_id" in agent_section:
                            yaml_data["node_id"] = agent_section["node_id"]
                        if "heartbeat_interval_seconds" in agent_section:
                            yaml_data["heartbeat_interval_seconds"] = agent_section[
                                "heartbeat_interval_seconds"
                            ]
                        if "identity_path" in agent_section:
                            yaml_data["identity_path"] = Path(agent_section["identity_path"])

        # Environment variables take precedence over YAML values
        env_kwargs: dict[str, Any] = {}
        if "SENTINELX_CONTROLLER_URL" in os.environ:
            env_kwargs["controller_url"] = os.environ["SENTINELX_CONTROLLER_URL"]
        if "SENTINELX_NODE_ID" in os.environ:
            env_kwargs["node_id"] = os.environ["SENTINELX_NODE_ID"]
        if "SENTINELX_ENROLLMENT_TOKEN" in os.environ:
            env_kwargs["enrollment_token"] = os.environ["SENTINELX_ENROLLMENT_TOKEN"]
        if "SENTINELX_HEARTBEAT_INTERVAL" in os.environ:
            env_kwargs["heartbeat_interval_seconds"] = int(
                os.environ["SENTINELX_HEARTBEAT_INTERVAL"]
            )
        if "SENTINELX_IDENTITY_PATH" in os.environ:
            env_kwargs["identity_path"] = Path(os.environ["SENTINELX_IDENTITY_PATH"])

        merged = {**yaml_data, **env_kwargs}
        return cls(**merged)
