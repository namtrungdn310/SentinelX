"""M2 deterministic tests: packet decoding, overlap, bounds and failure isolation."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from pydantic import ValidationError
from scapy.layers.inet import ICMP, IP, TCP, UDP
from scapy.layers.inet6 import IPv6
from scapy.layers.l2 import ARP, Ether
from scapy.packet import Raw

from sentinelx_agent.client import ControllerClient, ControllerClientError
from sentinelx_agent.config import AgentSettings
from sentinelx_agent.daemon import AgentDaemon
from sentinelx_agent.identity import AgentIdentity, AgentIdentityManager
from sentinelx_agent.network import runtime
from sentinelx_agent.network.aggregation import PacketObservation, SlidingWindowAggregator
from sentinelx_agent.network.capture import decode_packet
from sentinelx_common.contracts.agents import HeartbeatResponse
from sentinelx_common.contracts.network import NetworkBatchRequest, NetworkWindow
from sentinelx_common.contracts.telemetry import MetricBatchResponse

NOW = datetime(2026, 11, 4, tzinfo=UTC)
NODE = "11111111-2222-3333-4444-555555555555"
AGENT = "22222222-3333-4444-5555-666666666666"


def aggregator(**kwargs: Any) -> SlidingWindowAggregator:
    return SlidingWindowAggregator("eth0", start_monotonic=0, start_utc=NOW, **kwargs)


def observation(port: int = 443, source: str = "192.0.2.1") -> PacketObservation:
    return PacketObservation(source, "192.0.2.2", "tcp", 60, port, 0x12)


@pytest.mark.parametrize(
    "packet,protocol,flags,port",
    [
        (
            Ether()
            / IP(src="192.0.2.1", dst="192.0.2.2")
            / TCP(dport=443, flags="SA")
            / Raw(b"private-body-not-retained"),
            "tcp",
            0x12,
            443,
        ),
        (IPv6(src="2001:db8::1", dst="2001:db8::2") / UDP(dport=53), "udp", 0, 53),
        (
            IP(src="192.0.2.1", dst="192.0.2.2")
            / ICMP()
            / IP(src="198.51.100.1", dst="198.51.100.2")
            / TCP(flags="S"),
            "icmp",
            0,
            None,
        ),
    ],
)
def test_decode_retains_only_outer_ip_metadata(
    packet: Any,
    protocol: str,
    flags: int,
    port: int | None,
) -> None:
    result = decode_packet(packet)
    assert result is not None
    assert result.protocol == protocol and result.tcp_flags == flags
    assert result.destination_port == port and result.byte_count > 0
    assert "private-body" not in repr(result)
    assert result.source_ip not in {"198.51.100.1", "198.51.100.2"}


def test_non_ip_and_noninitial_fragments() -> None:
    assert decode_packet(Ether() / ARP()) is None
    result = decode_packet(IP(src="192.0.2.1", dst="192.0.2.2", proto=6, frag=2) / Raw(b"x"))
    assert result is not None and result.destination_port is None and result.tcp_flags == 0


def test_overlapping_windows_and_exact_boundary() -> None:
    aggregate = aggregator()
    aggregate.add(observation(), 1)
    aggregate.add(observation(80), 6)
    assert aggregate.drain(9.99) == []
    first = aggregate.drain(10)[0]
    assert first.features[0].packet_count == 2
    assert first.features[0].syn_count == first.features[0].ack_count == 2
    assert first.features[0].destination_ports == [80, 443]
    aggregate.add(observation(8080), 10)  # excluded from [0,10), included in [5,15)
    second = aggregate.drain(15)[0]
    assert second.features[0].packet_count == 2
    assert second.features[0].destination_ports == [80, 8080]
    assert first.window_id != second.window_id
    assert (second.window_start - first.window_start).total_seconds() == 5


def test_group_and_port_bounds_are_reported() -> None:
    aggregate = aggregator(max_groups=1)
    for port in range(70):
        aggregate.add(observation(port), 1)
    aggregate.add(observation(source="198.51.100.1"), 2)
    window = aggregate.drain(10)[0]
    assert window.omitted_packets == 1
    assert window.features[0].packet_count == 70
    assert len(window.features[0].destination_ports) == 64
    assert window.features[0].ports_truncated


def test_empty_capture_window_and_long_scheduler_stall_are_distinct() -> None:
    aggregate = aggregator()
    assert aggregate.drain(10)[0].features == []
    aggregate.add(observation(), 1000)
    completed = aggregate.drain(1000)
    assert len(completed) == 16 and completed[0].skipped_windows > 0
    assert len(aggregate._states) <= 18


@pytest.mark.parametrize(
    "values",
    [
        {"network_capture_enabled": True},
        {"network_window_seconds": 10, "network_step_seconds": 3},
        {"network_window_seconds": 300, "network_step_seconds": 1},
        {"network_max_groups": 1025},
    ],
)
def test_invalid_capture_configuration(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        AgentSettings.model_validate(values)


def test_network_yaml_environment_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "agent.yaml"
    config.write_text("agent:\n  network_capture_enabled: true\n  network_interface: eth0\n")
    monkeypatch.setenv("SENTINELX_NETWORK_INTERFACE", "ens3")
    settings = AgentSettings.load(config)
    assert settings.network_capture_enabled and settings.network_interface == "ens3"
    assert not AgentSettings().network_capture_enabled


@pytest.mark.asyncio
async def test_failed_capture_keeps_heartbeat_and_resource_telemetry_running(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    identity = AgentIdentity(node_id=NODE, agent_id=AGENT, enrolled_at=NOW)
    path = tmp_path / "identity.json"
    AgentIdentityManager.save(path, identity)
    settings = AgentSettings(
        identity_path=path,
        network_capture_enabled=True,
        network_interface="missing",
        telemetry_interval_seconds=0.01,
        telemetry_batch_size=1,
    )
    stop = asyncio.Event()
    client = AsyncMock(spec=ControllerClient)
    client.send_heartbeat.return_value = HeartbeatResponse(received_at=NOW, next_interval_seconds=1)

    def metrics(request: object) -> MetricBatchResponse:
        stop.set()
        return MetricBatchResponse(processed_count=1, received_at=NOW)

    client.send_metrics.side_effect = metrics

    def fail(self: object) -> None:
        raise PermissionError("private details must not appear")

    monkeypatch.setattr("sentinelx_agent.network.capture.PacketCapture.start", fail)
    await asyncio.wait_for(AgentDaemon(settings, client=client).run(stop), timeout=3)
    client.send_heartbeat.assert_awaited()
    client.send_metrics.assert_awaited()
    client.send_network.assert_not_awaited()
    assert "capture unavailable" in caplog.text and "private details" not in caplog.text


@pytest.mark.asyncio
async def test_network_retry_preserves_window_ids_and_closes_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [0.0]
    stop = asyncio.Event()
    closed: list[bool] = []

    class Capture:
        running = True

        def __init__(self, interface: str, bpf: str, aggregate: SlidingWindowAggregator) -> None:
            self.aggregate = aggregate

        def start(self) -> None:
            self.aggregate.add(observation(), 0.1)

        def stop(self) -> None:
            closed.append(True)

    async def advance(event: asyncio.Event, seconds: float) -> None:
        clock[0] += seconds

    monkeypatch.setattr(runtime, "PacketCapture", Capture)
    monkeypatch.setattr(runtime, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(runtime, "wait_stop", advance)
    client = AsyncMock(spec=ControllerClient)
    batches: list[NetworkBatchRequest] = []

    async def send(request: NetworkBatchRequest) -> None:
        batches.append(request)
        if len(batches) == 1:
            raise ControllerClientError(503, "temporary")
        stop.set()

    client.send_network.side_effect = send
    settings = AgentSettings(
        network_capture_enabled=True,
        network_interface="eth0",
        network_window_seconds=1,
        network_step_seconds=1,
    )
    await runtime.run_network(
        settings, AgentIdentity(node_id=NODE, agent_id=AGENT, enrolled_at=NOW), client, stop
    )
    assert batches[0].windows[0].window_id == batches[1].windows[0].window_id
    assert batches[0].sequence == batches[1].sequence == 1 and closed == [True]


def test_window_rejects_naive_timestamps_and_payload() -> None:
    data = {
        "window_id": str(UUID(int=1)),
        "window_start": NOW.isoformat(),
        "window_end": "2026-11-04T00:00:10Z",
        "interface": "eth0",
        "features": [],
    }
    assert NetworkWindow.model_validate(data)
    with pytest.raises(ValidationError):
        NetworkWindow.model_validate({**data, "window_end": "2026-11-04T00:00:10"})
    with pytest.raises(ValidationError):
        NetworkWindow.model_validate({**data, "raw_payload": "must not be accepted"})
