"""Ordered resource evaluation, replay cursors and serializable detection state."""

import uuid
from collections import deque
from datetime import UTC, datetime
from typing import Any

from sentinelx_common.contracts.detection import DetectionEventContract, DetectionSeverity
from sentinelx_common.contracts.telemetry import MetricSample
from sentinelx_controller.modules.detection.detectors.base import BaseDetector
from sentinelx_controller.modules.detection.detectors.cpu import CpuThresholdDetector
from sentinelx_controller.modules.detection.detectors.disk import DiskSaturationDetector
from sentinelx_controller.modules.detection.detectors.memory import MemoryExhaustionDetector


class DetectionEngine:
    """Production evaluates transaction-owned state, without a shared node cache.

    process_samples remains useful for isolated tests/tools; its cache is bounded.
    """

    def __init__(
        self,
        window_size: int = 10,
        cooldown_seconds: int = 60,
        detectors: list[BaseDetector] | None = None,
        *,
        max_gap_seconds: int = 60,
        max_sample_age_seconds: int = 86400,
        future_skew_seconds: int = 30,
    ) -> None:
        if not 3 <= window_size <= 100 or min(cooldown_seconds, future_skew_seconds) < 0:
            raise ValueError("Invalid detection window/cooldown")
        if min(max_gap_seconds, max_sample_age_seconds) <= 0:
            raise ValueError("Detection age/gap limits must be positive")
        self._window_size, self._cooldown_seconds = window_size, cooldown_seconds
        self._max_gap, self._max_age, self._future_skew = (
            max_gap_seconds,
            max_sample_age_seconds,
            future_skew_seconds,
        )
        self._detectors = (
            detectors
            if detectors is not None
            else [
                CpuThresholdDetector(),
                MemoryExhaustionDetector(),
                DiskSaturationDetector(),
            ]
        )
        self._windows: dict[uuid.UUID, deque[MetricSample]] = {}
        self._last_alerts: dict[tuple[uuid.UUID, str], tuple[datetime, DetectionSeverity]] = {}

    def process_samples(
        self, node_id: uuid.UUID, new_samples: list[MetricSample], *, now: datetime | None = None
    ) -> list[DetectionEventContract]:
        if not new_samples:
            return []
        if node_id not in self._windows:
            if len(self._windows) >= 2048:
                self.clear_node_state(next(iter(self._windows)))
            self._windows[node_id] = deque(maxlen=self._window_size)
        window = self._windows[node_id]
        received = now or datetime.now(UTC)
        events: list[DetectionEventContract] = []
        for sample in sorted(new_samples, key=lambda item: item.observed_at):
            age = (received - sample.observed_at).total_seconds()
            if age > self._max_age or age < -self._future_skew:
                continue
            if window:
                gap = (sample.observed_at - window[-1].observed_at).total_seconds()
                if gap <= 0:
                    continue
                if gap > self._max_gap:
                    window.clear()
            window.append(sample)
            for detector in self._detectors:
                event = detector.evaluate(node_id, list(window))
                if event is not None and self._should_emit_alert(node_id, event):
                    self._last_alerts[(node_id, event.detector_name)] = (
                        event.detected_at,
                        event.severity,
                    )
                    events.append(event)
        return events

    def evaluate_state(
        self,
        node_id: uuid.UUID,
        samples: list[MetricSample],
        state: dict[str, Any],
        *,
        now: datetime | None = None,
    ) -> tuple[list[DetectionEventContract], dict[str, Any]]:
        """Return candidates/new state without mutating the shared engine or input state."""
        local = DetectionEngine(
            self._window_size,
            self._cooldown_seconds,
            self._detectors,
            max_gap_seconds=self._max_gap,
            max_sample_age_seconds=self._max_age,
            future_skew_seconds=self._future_skew,
        )
        local._windows[node_id] = deque(
            (MetricSample.model_validate(item) for item in state.get("samples", [])),
            maxlen=self._window_size,
        )
        for name, alert in state.get("alerts", {}).items():
            local._last_alerts[(node_id, name)] = (
                datetime.fromisoformat(alert["time"]),
                DetectionSeverity(alert["severity"]),
            )
        events = local.process_samples(node_id, samples, now=now)
        updated: dict[str, Any] = {
            "samples": [sample.model_dump(mode="json") for sample in local._windows[node_id]],
            "alerts": {
                name: {"time": stamp.isoformat(), "severity": severity.value}
                for (node, name), (stamp, severity) in local._last_alerts.items()
                if node == node_id
            },
        }
        return events, updated

    def _should_emit_alert(self, node_id: uuid.UUID, event: DetectionEventContract) -> bool:
        previous = self._last_alerts.get((node_id, event.detector_name))
        if previous is None:
            return True
        last_time, severity = previous
        return (
            severity != DetectionSeverity.CRITICAL and event.severity == DetectionSeverity.CRITICAL
        ) or (event.detected_at - last_time).total_seconds() >= self._cooldown_seconds

    def clear_node_state(self, node_id: uuid.UUID) -> None:
        self._windows.pop(node_id, None)
        for key in [key for key in self._last_alerts if key[0] == node_id]:
            self._last_alerts.pop(key, None)
