"""Unit tests for RealResourceCollector."""

from datetime import UTC
from unittest.mock import MagicMock

import pytest

from sentinelx_agent.collectors.base import MetricCollector
from sentinelx_agent.collectors.real import RealResourceCollector


def test_real_collector_implements_protocol() -> None:
    """Test RealResourceCollector satisfies MetricCollector protocol."""
    collector = RealResourceCollector()
    assert isinstance(collector, MetricCollector)


def test_real_collector_hardware_sampling_bounds() -> None:
    """Test sampling on real host produces metrics within valid bounds."""
    collector = RealResourceCollector()
    sample = collector.collect()

    assert 0.0 <= sample.cpu_percent <= 100.0
    assert 0.0 <= sample.memory_percent <= 100.0
    assert sample.disk_percent is not None
    assert 0.0 <= sample.disk_percent <= 100.0
    assert sample.network_rx_bytes is not None and sample.network_rx_bytes >= 0
    assert sample.network_tx_bytes is not None and sample.network_tx_bytes >= 0
    assert sample.observed_at.tzinfo == UTC


def test_real_collector_network_delta_calculation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test network delta calculation between consecutive samples."""
    mock_net_1 = MagicMock(bytes_recv=10000, bytes_sent=5000)
    mock_net_2 = MagicMock(bytes_recv=16000, bytes_sent=7500)

    # Lần 1: trong __init__ trả về mock_net_1
    monkeypatch.setattr("psutil.net_io_counters", MagicMock(return_value=mock_net_1))
    collector = RealResourceCollector()

    # Lần 2: trong collect trả về mock_net_2
    monkeypatch.setattr("psutil.net_io_counters", MagicMock(return_value=mock_net_2))
    sample = collector.collect()

    # Delta mong đợi: rx = 16000 - 10000 = 6000; tx = 7500 - 5000 = 2500
    assert sample.network_rx_bytes == 6000
    assert sample.network_tx_bytes == 2500


def test_real_collector_network_counter_reset_recovery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test network counter rollover / interface restart recovers safely without negative values."""
    mock_net_1 = MagicMock(bytes_recv=50000, bytes_sent=40000)
    mock_net_reset = MagicMock(bytes_recv=1000, bytes_sent=500)
    mock_net_next = MagicMock(bytes_recv=2200, bytes_sent=900)

    monkeypatch.setattr("psutil.net_io_counters", MagicMock(return_value=mock_net_1))
    collector = RealResourceCollector()

    # Gặp tình huống reset: counter nhỏ hơn mốc cũ
    monkeypatch.setattr("psutil.net_io_counters", MagicMock(return_value=mock_net_reset))
    sample_reset = collector.collect()
    assert sample_reset.network_rx_bytes == 0
    assert sample_reset.network_tx_bytes == 0

    # Lần tiếp theo đo bình thường so với mốc mới
    monkeypatch.setattr("psutil.net_io_counters", MagicMock(return_value=mock_net_next))
    sample_next = collector.collect()
    assert sample_next.network_rx_bytes == 1200
    assert sample_next.network_tx_bytes == 400


def test_real_collector_disk_permission_error_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test collector degrades gracefully to 0.0 when disk inspection raises an error."""
    monkeypatch.setattr(
        "psutil.disk_usage",
        MagicMock(side_effect=PermissionError("Permission denied")),
    )
    collector = RealResourceCollector()
    sample = collector.collect()
    assert sample.disk_percent == 0.0
