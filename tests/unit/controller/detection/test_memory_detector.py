"""Unit tests for MemoryExhaustionDetector."""

import uuid
from datetime import UTC, datetime, timedelta

from sentinelx_common.contracts.detection import DetectionSeverity
from sentinelx_common.contracts.telemetry import MetricSample
from sentinelx_controller.modules.detection.detectors.memory import MemoryExhaustionDetector


def test_memory_detector_normal_load_no_alert() -> None:
    """RAM bình thường (< 85%) không được sinh ra cảnh báo."""
    detector = MemoryExhaustionDetector(warning_threshold=85.0, consecutive_samples=3)
    node_id = uuid.uuid4()
    now = datetime.now(UTC)

    samples = [
        MetricSample(observed_at=now, cpu_percent=20.0, memory_percent=60.0),
        MetricSample(
            observed_at=now + timedelta(seconds=5), cpu_percent=20.0, memory_percent=65.0
        ),
        MetricSample(
            observed_at=now + timedelta(seconds=10), cpu_percent=20.0, memory_percent=70.0
        ),
    ]

    event = detector.evaluate(node_id, samples)
    assert event is None


def test_memory_detector_high_warning() -> None:
    """3 mẫu liên tiếp vượt ngưỡng 85% nhưng < 95% sinh ra HIGH."""
    detector = MemoryExhaustionDetector(
        warning_threshold=85.0,
        critical_threshold=95.0,
        consecutive_samples=3,
    )
    node_id = uuid.uuid4()
    now = datetime.now(UTC)

    samples = [
        MetricSample(observed_at=now, cpu_percent=20.0, memory_percent=87.0),
        MetricSample(
            observed_at=now + timedelta(seconds=5), cpu_percent=20.0, memory_percent=89.0
        ),
        MetricSample(
            observed_at=now + timedelta(seconds=10), cpu_percent=20.0, memory_percent=91.0
        ),
    ]

    event = detector.evaluate(node_id, samples)
    assert event is not None
    assert event.severity == DetectionSeverity.HIGH
    assert event.details.metric_name == "memory_percent"
    assert event.confidence_score >= 0.75


def test_memory_detector_critical_exhaustion() -> None:
    """3 mẫu liên tiếp vượt ngưỡng 95% sinh ra CRITICAL."""
    detector = MemoryExhaustionDetector(
        warning_threshold=85.0,
        critical_threshold=95.0,
        consecutive_samples=3,
    )
    node_id = uuid.uuid4()
    now = datetime.now(UTC)

    samples = [
        MetricSample(observed_at=now, cpu_percent=20.0, memory_percent=96.0),
        MetricSample(
            observed_at=now + timedelta(seconds=5), cpu_percent=20.0, memory_percent=97.0
        ),
        MetricSample(
            observed_at=now + timedelta(seconds=10), cpu_percent=20.0, memory_percent=98.0
        ),
    ]

    event = detector.evaluate(node_id, samples)
    assert event is not None
    assert event.severity == DetectionSeverity.CRITICAL
    assert event.confidence_score >= 0.85
