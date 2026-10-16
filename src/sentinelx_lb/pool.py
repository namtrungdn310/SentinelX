"""Upstream Backend instance and BackendPool management for SentinelX Load Balancer."""

from dataclasses import dataclass, field
from typing import Any

from sentinelx_lb.config import BackendConfig


@dataclass
class Backend:
    """Represents a single upstream backend server with active telemetry."""

    url: str
    name: str
    weight: int = 1
    is_healthy: bool = True
    in_flight: int = 0
    total_requests: int = 0
    success_requests: int = 0
    error_requests: int = 0

    def acquire(self) -> None:
        """Mark a new request being dispatched to this backend."""
        self.in_flight += 1
        self.total_requests += 1

    def release(self, status_code: int | None = None, is_error: bool = False) -> None:
        """Mark request completion and update outcome counters.

        Guarantees in_flight never drops below zero even on unexpected race conditions.
        """
        if self.in_flight > 0:
            self.in_flight -= 1

        if is_error or (status_code is not None and status_code >= 500):
            self.error_requests += 1
        else:
            self.success_requests += 1

    def to_dict(self) -> dict[str, Any]:
        """Serialize backend state for metrics and status inspection."""
        return {
            "name": self.name,
            "url": self.url,
            "weight": self.weight,
            "is_healthy": self.is_healthy,
            "in_flight": self.in_flight,
            "total_requests": self.total_requests,
            "success_requests": self.success_requests,
            "error_requests": self.error_requests,
        }


@dataclass
class BackendPool:
    """Manages the active set of upstream backends."""

    backends: list[Backend] = field(default_factory=list)

    @classmethod
    def from_configs(cls, configs: list[BackendConfig]) -> "BackendPool":
        """Instantiate a pool from configuration objects."""
        backends = [
            Backend(
                url=cfg.url,
                name=cfg.name or f"backend-{idx + 1}",
                weight=cfg.weight,
            )
            for idx, cfg in enumerate(configs)
        ]
        return cls(backends=backends)

    def get_available_backends(self) -> list[Backend]:
        """Return all healthy backends available for routing."""
        return [b for b in self.backends if b.is_healthy]

    def get_by_url(self, url: str) -> Backend | None:
        """Lookup a specific backend by its base URL."""
        cleaned = url.strip().rstrip("/")
        for b in self.backends:
            if b.url == cleaned:
                return b
        return None

    def stats(self) -> dict[str, Any]:
        """Aggregate pool-level telemetry metrics."""
        available = self.get_available_backends()
        return {
            "total_backends": len(self.backends),
            "healthy_backends": len(available),
            "total_in_flight": sum(b.in_flight for b in self.backends),
            "total_requests": sum(b.total_requests for b in self.backends),
            "total_success": sum(b.success_requests for b in self.backends),
            "total_errors": sum(b.error_requests for b in self.backends),
            "backends": [b.to_dict() for b in self.backends],
        }
