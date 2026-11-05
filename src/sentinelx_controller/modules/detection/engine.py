"""Detection Engine managing sliding-window state and anti-flapping logic."""

import logging
import uuid
from collections import deque
from datetime import datetime

from sentinelx_common.contracts.detection import DetectionEventContract, DetectionSeverity
from sentinelx_common.contracts.telemetry import MetricSample
from sentinelx_controller.modules.detection.detectors.base import BaseDetector
from sentinelx_controller.modules.detection.detectors.cpu import CpuThresholdDetector
from sentinelx_controller.modules.detection.detectors.disk import DiskSaturationDetector
from sentinelx_controller.modules.detection.detectors.memory import MemoryExhaustionDetector

logger = logging.getLogger(__name__)


class DetectionEngine:
    """Coordinates detectors, sliding windows per node, and event cooldown."""

    def __init__(
        self,
        window_size: int = 10,
        cooldown_seconds: int = 60,
        detectors: list[BaseDetector] | None = None,
    ) -> None:
        self._window_size = window_size
        self._cooldown_seconds = cooldown_seconds
        self._windows: dict[uuid.UUID, deque[MetricSample]] = {}
        # Key: (node_id, detector_name) -> Value: (last_alert_time, last_severity)
        self._last_alerts: dict[tuple[uuid.UUID, str], tuple[datetime, DetectionSeverity]] = {}

        self._detectors: list[BaseDetector] = detectors or [
            CpuThresholdDetector(),
            MemoryExhaustionDetector(),
            DiskSaturationDetector(),
        ]

    def process_samples(
        self,
        node_id: uuid.UUID,
        new_samples: list[MetricSample],
    ) -> list[DetectionEventContract]:
        """Process incoming metric batch and return newly generated detection events."""
        if not new_samples:
            return []

        # 1. Update sliding window for node
        if node_id not in self._windows:
            self._windows[node_id] = deque(maxlen=self._window_size)

        node_window = self._windows[node_id]
        for sample in new_samples:
            node_window.append(sample)

        window_list = list(node_window)
        events: list[DetectionEventContract] = []

        # 2. Evaluate with detectors
        for detector in self._detectors:
            try:
                event = detector.evaluate(node_id, window_list)
                if event is not None and self._should_emit_alert(node_id, event):
                    self._record_alert(node_id, event)
                    events.append(event)
            except Exception as exc:
                logger.error(
                    "Error executing detector %s on node %s: %s",
                    detector.name,
                    node_id,
                    exc,
                )

        return events

    def _should_emit_alert(
        self,
        node_id: uuid.UUID,
        event: DetectionEventContract,
    ) -> bool:
        """Anti-flapping and cooldown check."""
        key = (node_id, event.detector_name)
        if key not in self._last_alerts:
            return True

        last_time, last_severity = self._last_alerts[key]
        elapsed = (event.detected_at - last_time).total_seconds()

        # Severity escalation allows immediate alert
        if (
            last_severity != DetectionSeverity.CRITICAL
            and event.severity == DetectionSeverity.CRITICAL
        ):
            return True

        return elapsed >= self._cooldown_seconds

    def _record_alert(
        self,
        node_id: uuid.UUID,
        event: DetectionEventContract,
    ) -> None:
        """Record the latest emitted alert."""
        key = (node_id, event.detector_name)
        self._last_alerts[key] = (event.detected_at, event.severity)

    def clear_node_state(self, node_id: uuid.UUID) -> None:
        """Clear memory cache when a node is removed."""
        self._windows.pop(node_id, None)
        keys_to_remove = [k for k in self._last_alerts if k[0] == node_id]
        for k in keys_to_remove:
            self._last_alerts.pop(k, None)
