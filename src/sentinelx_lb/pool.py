"""Upstream Backend instance and BackendPool management for SentinelX Load Balancer."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sentinelx_lb.config import BackendConfig


class BackendHealthState(StrEnum):
    """Health lifecycle states of an upstream backend target."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    RECOVERING = "recovering"


@dataclass
class Backend:
    """Represents a single upstream backend server with active telemetry and health state."""

    url: str
    name: str
    weight: int = 1
    health_path: str | None = None
    is_healthy: bool = True
    health_state: BackendHealthState = BackendHealthState.HEALTHY

    # Request concurrency metrics
    in_flight: int = 0
    total_requests: int = 0
    success_requests: int = 0
    error_requests: int = 0

    # Active health probing metrics
    consecutive_successes: int = 0
    consecutive_failures: int = 0
    last_health_check_at: str | None = None
    last_health_status_code: int | None = None
    last_health_error: str | None = None

    # Flapping protection baseline
    flapping_detected: bool = False
    flapping_transitions: int = 0
    last_state_change_at: str | None = None

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

    def record_health_success(self, success_threshold: int, status_code: int = 200) -> bool:
        """Record a successful health probe.

        Returns True if the backend transitioned from ejected to re-added (HEALTHY).
        """
        now_iso = datetime.now(UTC).isoformat()
        self.consecutive_failures = 0
        self.consecutive_successes += 1
        self.last_health_check_at = now_iso
        self.last_health_status_code = status_code
        self.last_health_error = None

        # If recovering from unhealthy, transition state indicator
        if self.health_state == BackendHealthState.UNHEALTHY:
            self.health_state = BackendHealthState.RECOVERING

        # Flapping protection: require double successes if currently flapping
        effective_threshold = (
            success_threshold * 2 if self.flapping_detected else success_threshold
        )

        if self.consecutive_successes >= effective_threshold:
            # If flapping, clear flag once stable
            if self.consecutive_successes >= effective_threshold + 2:
                self.flapping_detected = False
                self.flapping_transitions = 0

            if not self.is_healthy:
                self.is_healthy = True
                self.health_state = BackendHealthState.HEALTHY
                self.flapping_transitions += 1
                self.last_state_change_at = now_iso
                return True

            self.health_state = BackendHealthState.HEALTHY

        return False

    def record_health_failure(
        self,
        failure_threshold: int,
        error_msg: str,
        status_code: int | None = None,
    ) -> bool:
        """Record a failed health probe.

        Returns True if the backend transitioned from healthy to ejected (UNHEALTHY).
        """
        now_iso = datetime.now(UTC).isoformat()
        self.consecutive_successes = 0
        self.consecutive_failures += 1
        self.last_health_check_at = now_iso
        self.last_health_status_code = status_code
        self.last_health_error = error_msg

        if self.health_state == BackendHealthState.HEALTHY:
            self.health_state = BackendHealthState.DEGRADED

        if self.consecutive_failures >= failure_threshold:
            if self.is_healthy:
                self.is_healthy = False
                self.health_state = BackendHealthState.UNHEALTHY
                self.flapping_transitions += 1
                self.last_state_change_at = now_iso

                # Check flapping: more than 3 state transitions marks backend as flapping
                if self.flapping_transitions >= 4:
                    self.flapping_detected = True

                return True

            self.health_state = BackendHealthState.UNHEALTHY

        return False

    def to_dict(self) -> dict[str, Any]:
        """Serialize backend state for metrics and status inspection."""
        return {
            "name": self.name,
            "url": self.url,
            "weight": self.weight,
            "is_healthy": self.is_healthy,
            "health_state": self.health_state.value,
            "in_flight": self.in_flight,
            "total_requests": self.total_requests,
            "success_requests": self.success_requests,
            "error_requests": self.error_requests,
            "consecutive_successes": self.consecutive_successes,
            "consecutive_failures": self.consecutive_failures,
            "last_health_check_at": self.last_health_check_at,
            "last_health_status_code": self.last_health_status_code,
            "last_health_error": self.last_health_error,
            "flapping_detected": self.flapping_detected,
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
                health_path=cfg.health_path,
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
