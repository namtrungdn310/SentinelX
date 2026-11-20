"""Replay/order, rate and evidence freshness regressions for the M4/M8 boundary."""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from sentinelx_common.contracts.network import NetworkFeature
from sentinelx_controller.modules.detection.detectors.traffic_spike import TrafficSpikeDetector
from sentinelx_controller.modules.detection.engine import DetectionEngine
from sentinelx_controller.modules.detection.service import DetectionService
from tests.unit.controller.detection.test_network_detectors import make_window


def feature(packets: int = 2000, direction: str = "inbound") -> NetworkFeature:
    return NetworkFeature.model_validate(
        {
            "source_ip": "198.51.100.6",
            "destination_ip": "192.0.2.11",
            "protocol": "tcp",
            "packet_count": packets,
            "byte_count": packets * 64,
            "direction": direction,
        }
    )


def test_future_replay_and_reordered_windows_do_not_poison_cursors() -> None:
    now, node = datetime.now(UTC), uuid4()
    engine = DetectionEngine()
    future = make_window([feature()], start=now + timedelta(hours=1))
    events, state = engine.evaluate_network_state(node, [future], {}, now=now)
    assert events == [] and not state.get("network_cursors")
    valid = make_window([feature()], duration_seconds=10, start=now - timedelta(seconds=10))
    events, state = engine.evaluate_network_state(node, [valid], state, now=now)
    assert events
    original = dict(state)
    for candidate in (
        valid,
        valid.model_copy(update={"window_id": uuid4()}),
        make_window([feature()], start=now - timedelta(seconds=30)),
    ):
        events, state = engine.evaluate_network_state(node, [candidate], state, now=now)
        assert events == [] and state["network_cursors"] == original["network_cursors"]


def test_rate_threshold_is_duration_independent_and_outbound_is_not_attack() -> None:
    detector, node = TrafficSpikeDetector(), uuid4()
    short = make_window([feature(600)], duration_seconds=5)
    long = make_window([feature(2400)], duration_seconds=20)
    assert len(detector.evaluate(node, short)) == len(detector.evaluate(node, long)) == 1
    assert detector.evaluate(node, make_window([feature(100000, "outbound")])) == []


def test_anomaly_watermark_is_monotonic_across_observation_streams() -> None:
    now, node = datetime.now(UTC), uuid4()
    window = make_window([feature()], start=now - timedelta(seconds=15))
    state: dict[str, Any] = {"last_anomaly_at": now.isoformat()}
    _, updated = DetectionEngine().evaluate_network_state(node, [window], state, now=now)
    assert updated["last_anomaly_at"] == now.isoformat()


@pytest.mark.asyncio
async def test_recovery_requires_fresh_complete_quiet_observation() -> None:
    now = datetime.now(UTC)
    quiet = now - timedelta(seconds=120)
    repository = AsyncMock()
    service = DetectionService(repository, DetectionEngine())
    state: dict[str, Any] = {
        "last_anomaly_at": (quiet - timedelta(seconds=1)).isoformat(),
        "network_observed_at": now.isoformat(),
        "network_observation_complete": True,
    }
    repository.incident_states.return_value = [state]
    assert await service.observed_quiet(uuid4(), quiet, network=True)
    for field, value in (
        ("network_observation_complete", False),
        ("network_observed_at", quiet.isoformat()),
        ("last_anomaly_at", now.isoformat()),
    ):
        repository.incident_states.return_value = [{**state, field: value}]
        assert not await service.observed_quiet(uuid4(), quiet, network=True)
    repository.incident_states.return_value = []
    assert not await service.observed_quiet(uuid4(), quiet, network=True)
