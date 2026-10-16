"""Configuration settings for SentinelX HTTP Load Balancer."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LBAlgorithm(StrEnum):
    """Supported load balancing distribution algorithms."""

    ROUND_ROBIN = "round_robin"
    LEAST_IN_FLIGHT = "least_in_flight"


class BackendConfig(BaseModel):
    """Configuration for an upstream backend target."""

    url: str = Field(..., description="Base URL of upstream backend, e.g. http://10.0.1.20:8000")
    weight: int = Field(default=1, ge=1, description="Traffic weight for future weighted routing")
    name: str | None = Field(default=None, description="Optional human-readable backend label")

    @field_validator("url")
    @classmethod
    def normalize_url(cls, v: str) -> str:
        """Strip trailing slash to keep URL join predictable."""
        cleaned = v.strip().rstrip("/")
        if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
            raise ValueError(f"Backend URL must start with http:// or https://: '{v}'")
        return cleaned


class LBSettings(BaseSettings):
    """Load Balancer process settings loaded from environment or config file.

    Prefix: SENTINELX_LB_
    Example:
        SENTINELX_LB_PORT=8080
        SENTINELX_LB_ALGORITHM=least_in_flight
        SENTINELX_LB_BACKENDS="http://10.0.1.20:8000,http://10.0.1.21:8000"
    """

    model_config = SettingsConfigDict(
        env_prefix="SENTINELX_LB_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    host: str = Field(default="0.0.0.0", description="IP address to bind the LB listener")
    port: int = Field(default=8080, ge=1, le=65535, description="Port to bind the LB listener")
    algorithm: LBAlgorithm = Field(
        default=LBAlgorithm.ROUND_ROBIN,
        description="Active routing strategy (round_robin or least_in_flight)",
    )
    backends: list[BackendConfig] = Field(
        default_factory=list,
        description="List of upstream backend servers",
    )
    client_timeout_seconds: float = Field(
        default=30.0,
        ge=0.5,
        description="Timeout for forwarding requests to upstream backend",
    )
    log_level: str = Field(default="INFO", description="Logging level")

    @field_validator("backends", mode="before")
    @classmethod
    def parse_backends(cls, v: Any) -> Any:
        """Support comma-separated string from env: 'http://h1:8000,http://h2:8000'."""
        if isinstance(v, str):
            urls = [item.strip() for item in v.split(",") if item.strip()]
            return [{"url": u} for u in urls]
        return v
