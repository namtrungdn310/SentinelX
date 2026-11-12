"""Unit tests for CpuThresholdDetector."""

import uuid
from datetime import UTC, datetime, timedelta

from sentinelx_common.contracts.detection import DetectionSeverity, ResourceAnomalyDetail
from sentinelx_common.contracts.telemetry import MetricSample
from sentinelx_controller.modules.detection.detectors.cpu import CpuThresholdDetector


def test_cpu_detector_normal_load_no_alert() -> None:
    """CPU bình thường (< 80%) không được sinh ra cảnh báo."""
    detector = CpuThresholdDetector(warning_threshold=80.0, consecutive_samples=3)
    node_id = uuid.uuid4()
    now = datetime.now(UTC)

    samples = [
        MetricSample(observed_at=now, cpu_percent=30.0, memory_percent=40.0),
        MetricSample(
            observed_at=now + timedelta(seconds=5), cpu_percent=45.0, memory_percent=40.0
        ),
        MetricSample(
            observed_at=now + timedelta(seconds=10), cpu_percent=50.0, memory_percent=40.0
        ),
    ]

    event = detector.evaluate(node_id, samples)
    assert event is None


def test_cpu_detector_spike_suppression() -> None:
    """Spike tức thời (chỉ 1 mẫu vọt lên) phải bị loại bỏ."""
    detector = CpuThresholdDetector(warning_threshold=80.0, consecutive_samples=3)
    node_id = uuid.uuid4()
    now = datetime.now(UTC)

    samples = [
        MetricSample(observed_at=now, cpu_percent=30.0, memory_percent=40.0),
        MetricSample(
            observed_at=now + timedelta(seconds=5), cpu_percent=98.0, memory_percent=40.0
        ),
        MetricSample(
            observed_at=now + timedelta(seconds=10), cpu_percent=35.0, memory_percent=40.0
        ),
    ]

    event = detector.evaluate(node_id, samples)
    assert event is None


def test_cpu_detector_sustained_overload_triggers_high() -> None:
    """3 mẫu liên tiếp vượt ngưỡng 80% sinh ra event HIGH."""
    detector = CpuThresholdDetector(
        warning_threshold=80.0,
        critical_threshold=95.0,
        consecutive_samples=3,
    )
    node_id = uuid.uuid4()
    now = datetime.now(UTC)

    samples = [
        MetricSample(observed_at=now, cpu_percent=85.0, memory_percent=40.0),
        MetricSample(
            observed_at=now + timedelta(seconds=5), cpu_percent=88.0, memory_percent=40.0
        ),
        MetricSample(
            observed_at=now + timedelta(seconds=10), cpu_percent=91.0, memory_percent=40.0
        ),
    ]

    event = detector.evaluate(node_id, samples)
    assert event is not None
    assert event.severity == DetectionSeverity.HIGH
    assert isinstance(event.details, ResourceAnomalyDetail)
    assert event.details.metric_name == "cpu_percent"
    assert event.details.current_value == 91.0
    assert event.confidence_score >= 0.70


def test_cpu_detector_critical_overload() -> None:
    """3 mẫu liên tiếp vượt ngưỡng 95% sinh ra event CRITICAL."""
    detector = CpuThresholdDetector(
        warning_threshold=80.0,
        critical_threshold=95.0,
        consecutive_samples=3,
    )
    node_id = uuid.uuid4()
    now = datetime.now(UTC)

    samples = [
        MetricSample(observed_at=now, cpu_percent=96.0, memory_percent=40.0),
        MetricSample(
            observed_at=now + timedelta(seconds=5), cpu_percent=98.0, memory_percent=40.0
        ),
        MetricSample(
            observed_at=now + timedelta(seconds=10), cpu_percent=99.0, memory_percent=40.0
        ),
    ]

    event = detector.evaluate(node_id, samples)
    assert event is not None
    assert event.severity == DetectionSeverity.CRITICAL
    assert event.confidence_score >= 0.90
