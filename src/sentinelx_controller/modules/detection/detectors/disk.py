"""Disk saturation anomaly detector."""

import uuid
from datetime import UTC, datetime

from sentinelx_common.contracts.detection import (
    DetectionEventContract,
    DetectionSeverity,
    DetectorType,
    ResourceAnomalyDetail,
)
from sentinelx_common.contracts.telemetry import MetricSample
from sentinelx_controller.modules.detection.detectors.base import BaseDetector


class DiskSaturationDetector(BaseDetector):
    """Phát hiện dung lượng ổ đĩa sắp cạn kiệt."""

    def __init__(
        self,
        warning_threshold: float = 85.0,
        critical_threshold: float = 95.0,
    ) -> None:
        self._warning_threshold = warning_threshold
        self._critical_threshold = critical_threshold

    @property
    def name(self) -> str:
        return DetectorType.DISK_SATURATION.value

    def evaluate(
        self,
        node_id: uuid.UUID,
        window_samples: list[MetricSample],
    ) -> DetectionEventContract | None:
        """Đánh giá mẫu dung lượng ổ đĩa."""
        if not window_samples:
            return None

        latest_sample = window_samples[-1]
        if latest_sample.disk_percent is None:
            return None

        disk_pct = latest_sample.disk_percent
        if disk_pct >= self._critical_threshold:
            severity = DetectionSeverity.CRITICAL
            active_threshold = self._critical_threshold
        elif disk_pct >= self._warning_threshold:
            severity = DetectionSeverity.HIGH
            active_threshold = self._warning_threshold
        else:
            return None

        confidence = 0.95 if severity == DetectionSeverity.CRITICAL else 0.85

        return DetectionEventContract(
            node_id=str(node_id),
            detector_name=self.name,
            severity=severity,
            attacker_ip=None,
            confidence_score=confidence,
            details=ResourceAnomalyDetail(
                metric_name="disk_percent",
                current_value=round(disk_pct, 2),
                threshold_value=active_threshold,
                window_duration_seconds=0,
                consecutive_samples=1,
            ),
            detected_at=latest_sample.observed_at or datetime.now(UTC),
        )
