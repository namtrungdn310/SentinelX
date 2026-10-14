"""Unit tests for TelemetryBatcher buffer."""

from datetime import UTC, datetime

from sentinelx_agent.telemetry import TelemetryBatcher
from sentinelx_common.contracts.telemetry import MetricSample


def _sample(cpu: float) -> MetricSample:
    return MetricSample(
        observed_at=datetime.now(UTC),
        cpu_percent=cpu,
        memory_percent=50.0,
    )


def test_batcher_add_and_len() -> None:
    """Test batcher stores samples and updates length."""
    batcher = TelemetryBatcher(max_buffer_size=10)
    assert len(batcher) == 0
    assert not batcher.is_ready(3)

    batcher.add(_sample(10.0))
    batcher.add(_sample(20.0))
    assert len(batcher) == 2
    assert not batcher.is_ready(3)

    batcher.add(_sample(30.0))
    assert len(batcher) == 3
    assert batcher.is_ready(3)


def test_batcher_drain_order_and_count() -> None:
    """Test batcher drains FIFO order and respects count."""
    batcher = TelemetryBatcher(max_buffer_size=10)
    batcher.add(_sample(10.0))
    batcher.add(_sample(20.0))
    batcher.add(_sample(30.0))

    drained = batcher.drain(2)
    assert len(drained) == 2
    assert drained[0].cpu_percent == 10.0
    assert drained[1].cpu_percent == 20.0
    assert len(batcher) == 1

    remaining = batcher.drain()
    assert len(remaining) == 1
    assert remaining[0].cpu_percent == 30.0
    assert len(batcher) == 0


def test_batcher_max_buffer_overflow() -> None:
    """Test batcher drops oldest when max capacity is exceeded."""
    batcher = TelemetryBatcher(max_buffer_size=2)
    batcher.add(_sample(10.0))
    batcher.add(_sample(20.0))
    batcher.add(_sample(30.0))

    assert len(batcher) == 2
    drained = batcher.drain()
    # Oldest (10.0) was dropped
    assert drained[0].cpu_percent == 20.0
    assert drained[1].cpu_percent == 30.0
