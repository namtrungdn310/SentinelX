"""Unit tests for DiskSaturationDetector."""

import uuid
from datetime import UTC, datetime

from sentinelx_common.contracts.detection import DetectionSeverity
from sentinelx_common.contracts.telemetry import MetricSample
from sentinelx_controller.modules.detection.detectors.disk import DiskSaturationDetector


def test_disk_detector_normal_usage() -> None:
    """Disk dưới 85% không sinh ra alert."""
    detector = DiskSaturationDetector(warning_threshold=85.0, critical_threshold=95.0)
    node_id = uuid.uuid4()
    now = datetime.now(UTC)

    samples = [
        MetricSample(observed_at=now, cpu_percent=20.0, memory_percent=40.0, disk_percent=55.0),
    ]

    event = detector.evaluate(node_id, samples)
    assert event is None


def test_disk_detector_high_and_critical() -> None:
    """Kiểm tra disk vượt ngưỡng HIGH (88%) và CRITICAL (96%)."""
    detector = DiskSaturationDetector(warning_threshold=85.0, critical_threshold=95.0)
    node_id = uuid.uuid4()
    now = datetime.now(UTC)

    # HIGH
    event_high = detector.evaluate(
        node_id,
        [MetricSample(observed_at=now, cpu_percent=20.0, memory_percent=40.0, disk_percent=88.0)],
    )
    assert event_high is not None
    assert event_high.severity == DetectionSeverity.HIGH

    # CRITICAL
    event_crit = detector.evaluate(
        node_id,
        [MetricSample(observed_at=now, cpu_percent=20.0, memory_percent=40.0, disk_percent=96.0)],
    )
    assert event_crit is not None
    assert event_crit.severity == DetectionSeverity.CRITICAL
