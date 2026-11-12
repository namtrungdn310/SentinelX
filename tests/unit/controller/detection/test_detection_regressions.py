"""Batch boundaries, transport replay and transactional state cannot alter anomaly semantics."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from sentinelx_common.contracts.detection import ResourceAnomalyDetail
from sentinelx_common.contracts.telemetry import MetricSample
from sentinelx_controller.modules.detection.engine import DetectionEngine

NOW = datetime(2026, 11, 6, tzinfo=UTC)


def samples(values: list[float], start: int = 0) -> list[MetricSample]:
    return [
        MetricSample(
            observed_at=NOW + timedelta(seconds=start + i * 5), cpu_percent=value, memory_percent=40
        )
        for i, value in enumerate(values)
    ]


def test_overload_then_recovery_is_detected_within_default_five_sample_batch() -> None:
    events = DetectionEngine().process_samples(uuid4(), samples([98, 98, 98, 20, 20]), now=NOW)
    assert len(events) == 1 and events[0].severity == "CRITICAL"
    assert events[0].detected_at == NOW + timedelta(seconds=10)


@pytest.mark.parametrize("cuts", [[6], [1, 1, 1, 1, 1, 1], [2, 4], [3, 3]])
def test_batch_partition_does_not_change_warning_or_escalation(cuts: list[int]) -> None:
    engine, node = DetectionEngine(), uuid4()
    batch = samples([85, 85, 85, 98, 98, 98])
    events, offset = [], 0
    for count in cuts:
        events.extend(engine.process_samples(node, batch[offset : offset + count], now=NOW))
        offset += count
    assert [(event.severity.value, event.detected_at) for event in events] == [
        ("HIGH", NOW + timedelta(seconds=10)),
        ("CRITICAL", NOW + timedelta(seconds=25)),
    ]


def test_duplicate_and_late_samples_do_not_advance_consecutive_count() -> None:
    engine, node = DetectionEngine(), uuid4()
    sample = samples([98])[0]
    for _ in range(3):
        assert engine.process_samples(node, [sample], now=NOW) == []
    assert engine.process_samples(node, samples([98], start=-5), now=NOW) == []
    events = engine.process_samples(node, samples([98, 98], start=5), now=NOW)
    assert len(events) == 1
    assert engine.process_samples(node, samples([98, 98, 98]), now=NOW) == []


def test_unsorted_batch_is_evaluated_chronologically() -> None:
    events = DetectionEngine().process_samples(
        uuid4(), list(reversed(samples([98, 98, 98]))), now=NOW
    )
    assert (
        len(events) == 1
        and isinstance(events[0].details, ResourceAnomalyDetail)
        and events[0].details.window_duration_seconds == 10
    )


def test_long_gap_breaks_consecutive_sequence() -> None:
    engine, node = DetectionEngine(), uuid4()
    assert engine.process_samples(node, samples([98, 98]), now=NOW) == []
    assert (
        engine.process_samples(node, samples([98], start=80), now=NOW + timedelta(seconds=80)) == []
    )


def test_stale_or_future_samples_are_ignored_without_advancing_watermark() -> None:
    engine, node = DetectionEngine(), uuid4()
    assert engine.process_samples(node, samples([98] * 3, start=-90000), now=NOW) == []
    assert engine.process_samples(node, samples([98] * 3, start=300), now=NOW) == []
    assert len(engine.process_samples(node, samples([98] * 3), now=NOW)) == 1


def test_evaluate_state_is_pure_and_survives_new_engine_without_replaying() -> None:
    node = uuid4()
    original: dict[str, Any] = {}
    events, state = DetectionEngine().evaluate_state(node, samples([98] * 3), original, now=NOW)
    assert original == {} and len(events) == 1
    assert len(state["samples"]) == 3
    again, restored = DetectionEngine().evaluate_state(node, samples([98] * 3), state, now=NOW)
    assert again == [] and restored == state
    # If the transaction rolls back, reuse the OLD state, not the uncommitted candidate.
    retry, _ = DetectionEngine().evaluate_state(node, samples([98] * 3), original, now=NOW)
    assert len(retry) == 1


def test_naive_timestamps_rejected_and_offsets_normalized() -> None:
    with pytest.raises(ValidationError):
        MetricSample(observed_at=NOW.replace(tzinfo=None), cpu_percent=98, memory_percent=40)
    sample = MetricSample.model_validate(
        {"observed_at": "2026-11-06T07:00:00+07:00", "cpu_percent": 98, "memory_percent": 40}
    )
    assert sample.observed_at == NOW and sample.observed_at.tzinfo == UTC
