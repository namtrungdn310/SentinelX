"""Unit tests for FakeMetricGenerator."""

from datetime import UTC, datetime

from sentinelx_agent.collectors.fake import FakeMetricGenerator


def test_fake_metric_generator_output_bounds() -> None:
    """Test fake metric generator outputs within realistic ranges."""
    collector = FakeMetricGenerator()

    for _ in range(50):
        sample = collector.generate_sample()
        assert 0.0 <= sample.cpu_percent <= 100.0
        assert 0.0 <= sample.memory_percent <= 100.0
        assert sample.disk_percent is not None
        assert 0.0 <= sample.disk_percent <= 100.0
        assert sample.network_rx_bytes is not None and sample.network_rx_bytes >= 0
        assert sample.network_tx_bytes is not None and sample.network_tx_bytes >= 0
        assert sample.observed_at is not None


def test_fake_metric_generator_custom_time() -> None:
    """Test fake metric generator respects custom observed_at timestamp."""
    collector = FakeMetricGenerator()
    fixed_time = datetime(2026, 10, 14, 12, 0, 0, tzinfo=UTC)

    sample = collector.generate_sample(observed_at=fixed_time)
    assert sample.observed_at == fixed_time
