"""Unit tests for DetectionEngine anti-flapping and coordination."""

import uuid
from datetime import UTC, datetime, timedelta

from sentinelx_common.contracts.detection import DetectionSeverity
from sentinelx_common.contracts.telemetry import MetricSample
from sentinelx_controller.modules.detection.engine import DetectionEngine


def test_detection_engine_cooldown_prevents_spam() -> None:
    """Cơ chế Cooldown ngăn không cho bắn spam cảnh báo liên tục."""
    engine = DetectionEngine(cooldown_seconds=60)
    node_id = uuid.uuid4()
    now = datetime.now(UTC)

    batch1 = [
        MetricSample(observed_at=now, cpu_percent=90.0, memory_percent=40.0),
        MetricSample(
            observed_at=now + timedelta(seconds=5), cpu_percent=90.0, memory_percent=40.0
        ),
        MetricSample(
            observed_at=now + timedelta(seconds=10), cpu_percent=90.0, memory_percent=40.0
        ),
    ]
    events1 = engine.process_samples(node_id, batch1)
    assert len(events1) == 1
    assert events1[0].severity == DetectionSeverity.HIGH

    # Mẫu thứ 4 vẫn quá tải nhưng nằm trong thời gian cooldown 60s
    batch2 = [
        MetricSample(
            observed_at=now + timedelta(seconds=15), cpu_percent=90.0, memory_percent=40.0
        ),
    ]
    events2 = engine.process_samples(node_id, batch2)
    assert len(events2) == 0


def test_detection_engine_escalation_bypasses_cooldown() -> None:
    """Khi tình trạng leo thang lên CRITICAL, được phép bỏ qua Cooldown."""
    engine = DetectionEngine(cooldown_seconds=60)
    node_id = uuid.uuid4()
    now = datetime.now(UTC)

    batch1 = [
        MetricSample(observed_at=now, cpu_percent=85.0, memory_percent=40.0),
        MetricSample(
            observed_at=now + timedelta(seconds=5), cpu_percent=85.0, memory_percent=40.0
        ),
        MetricSample(
            observed_at=now + timedelta(seconds=10), cpu_percent=85.0, memory_percent=40.0
        ),
    ]
    events1 = engine.process_samples(node_id, batch1)
    assert len(events1) == 1
    assert events1[0].severity == DetectionSeverity.HIGH

    # Chỉ 5 giây sau vọt lên 98% (CRITICAL)
    batch2 = [
        MetricSample(
            observed_at=now + timedelta(seconds=15), cpu_percent=98.0, memory_percent=40.0
        ),
        MetricSample(
            observed_at=now + timedelta(seconds=20), cpu_percent=98.0, memory_percent=40.0
        ),
        MetricSample(
            observed_at=now + timedelta(seconds=25), cpu_percent=98.0, memory_percent=40.0
        ),
    ]
    events2 = engine.process_samples(node_id, batch2)
    assert len(events2) == 1
    assert events2[0].severity == DetectionSeverity.CRITICAL


def test_detection_engine_clear_state() -> None:
    """Xóa state bộ nhớ cache khi node bị xóa."""
    engine = DetectionEngine(cooldown_seconds=60)
    node_id = uuid.uuid4()
    now = datetime.now(UTC)

    batch = [
        MetricSample(observed_at=now, cpu_percent=90.0, memory_percent=40.0),
        MetricSample(
            observed_at=now + timedelta(seconds=5), cpu_percent=90.0, memory_percent=40.0
        ),
        MetricSample(
            observed_at=now + timedelta(seconds=10), cpu_percent=90.0, memory_percent=40.0
        ),
    ]
    engine.process_samples(node_id, batch)
    assert node_id in engine._windows

    engine.clear_node_state(node_id)
    assert node_id not in engine._windows
