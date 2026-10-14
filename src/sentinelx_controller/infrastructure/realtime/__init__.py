"""Realtime infrastructure package for SentinelX Controller."""

from sentinelx_controller.infrastructure.realtime.hub import RealtimeHub

_global_hub: RealtimeHub | None = None


def get_realtime_hub() -> RealtimeHub:
    """Dependency provider returning singleton RealtimeHub instance."""
    global _global_hub
    if _global_hub is None:
        _global_hub = RealtimeHub()
    return _global_hub


def reset_realtime_hub() -> None:
    """Reset singleton instance (useful in test teardown)."""
    global _global_hub
    _global_hub = None


__all__ = ["RealtimeHub", "get_realtime_hub", "reset_realtime_hub"]
