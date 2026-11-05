"""Memory exhaustion anomaly detector."""

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


class MemoryExhaustionDetector(BaseDetector):
    """Phát hiện cạn kiệt bộ nhớ RAM nghiêm trọng."""

    def __init__(
        self,
        warning_threshold: float = 85.0,
        critical_threshold: float = 95.0,
        consecutive_samples: int = 3,
    ) -> None:
        self._warning_threshold = warning_threshold
        self._critical_threshold = critical_threshold
        self._consecutive_samples = consecutive_samples

    @property
    def name(self) -> str:
        return DetectorType.MEMORY_EXHAUSTION.value

    def evaluate(
        self,
        node_id: uuid.UUID,
        window_samples: list[MetricSample],
    ) -> DetectionEventContract | None:
        """Đánh giá chuỗi mẫu metric RAM."""
        if len(window_samples) < self._consecutive_samples:
            return None

        recent_samples = window_samples[-self._consecutive_samples :]

        if all(s.memory_percent >= self._critical_threshold for s in recent_samples):
            severity = DetectionSeverity.CRITICAL
            active_threshold = self._critical_threshold
        elif all(s.memory_percent >= self._warning_threshold for s in recent_samples):
            severity = DetectionSeverity.HIGH
            active_threshold = self._warning_threshold
        else:
            return None

        latest_sample = recent_samples[-1]
        earliest_sample = recent_samples[0]
        duration_seconds = max(
            0,
            int((latest_sample.observed_at - earliest_sample.observed_at).total_seconds()),
        )

        excess_ratio = (latest_sample.memory_percent - active_threshold) / max(
            1.0, (100.0 - active_threshold)
        )
        confidence = min(1.0, max(0.75, 0.75 + 0.25 * excess_ratio))

        return DetectionEventContract(
            node_id=str(node_id),
            detector_name=self.name,
            severity=severity,
            attacker_ip=None,
            confidence_score=round(confidence, 3),
            details=ResourceAnomalyDetail(
                metric_name="memory_percent",
                current_value=round(latest_sample.memory_percent, 2),
                threshold_value=active_threshold,
                window_duration_seconds=duration_seconds,
                consecutive_samples=self._consecutive_samples,
                extra_context={
                    "window_memory_values": [round(s.memory_percent, 2) for s in recent_samples]
                },
            ),
            detected_at=latest_sample.observed_at or datetime.now(UTC),
        )
