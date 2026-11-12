"""Unit tests for Network Detectors and Network Detection Engine (Milestone M4)."""

import ipaddress
import uuid
from datetime import UTC, datetime, timedelta

from sentinelx_common.contracts.detection import DetectionSeverity, NetworkAnomalyDetail
from sentinelx_common.contracts.network import NetworkFeature, NetworkWindow
from sentinelx_controller.modules.detection.detectors.port_scan import PortScanDetector
from sentinelx_controller.modules.detection.detectors.syn_flood import SynFloodDetector
from sentinelx_controller.modules.detection.detectors.traffic_spike import TrafficSpikeDetector
from sentinelx_controller.modules.detection.engine import DetectionEngine


def make_window(
    features: list[NetworkFeature],
    duration_seconds: int = 5,
    start: datetime | None = None,
) -> NetworkWindow:
    t_start = start or datetime.now(UTC)
    t_end = t_start + timedelta(seconds=duration_seconds)
    return NetworkWindow(
        window_id=uuid.uuid4(),
        window_start=t_start,
        window_end=t_end,
        interface="eth0",
        features=features,
    )


# ─── 1. SYN FLOOD DETECTOR TESTS ───

def test_syn_flood_detector_normal_traffic_no_alert() -> None:
    detector = SynFloodDetector(min_syn=50, syn_ack_ratio=3.0)
    node_id = uuid.uuid4()
    feature = NetworkFeature(
        source_ip=ipaddress.ip_address("192.168.1.50"),
        destination_ip=ipaddress.ip_address("192.168.1.100"),
        protocol="tcp",
        packet_count=100,
        byte_count=5000,
        syn_count=40,
        ack_count=40,
        destination_ports=[80],
    )
    window = make_window([feature])
    events = detector.evaluate(node_id, window)
    assert events == []


def test_syn_flood_detector_triggers_high() -> None:
    detector = SynFloodDetector(min_syn=50, syn_ack_ratio=3.0)
    node_id = uuid.uuid4()
    feature = NetworkFeature(
        source_ip=ipaddress.ip_address("203.0.113.195"),
        destination_ip=ipaddress.ip_address("192.168.1.100"),
        protocol="tcp",
        packet_count=120,
        byte_count=6000,
        syn_count=80,
        ack_count=10,  # ratio = 8.0 >= 3.0
        destination_ports=[80],
    )
    window = make_window([feature])
    events = detector.evaluate(node_id, window)

    assert len(events) == 1
    event = events[0]
    assert event.detector_name == "syn_flood_detector"
    assert event.attacker_ip == "203.0.113.195"
    assert event.severity == DetectionSeverity.HIGH
    assert isinstance(event.details, NetworkAnomalyDetail)
    assert event.details.attack_type == "SYN_FLOOD"
    assert event.details.metric_ratio == 8.0


def test_syn_flood_detector_triggers_critical_on_no_ack_or_high_volume() -> None:
    detector = SynFloodDetector(min_syn=50, syn_ack_ratio=3.0)
    node_id = uuid.uuid4()
    feature = NetworkFeature(
        source_ip=ipaddress.ip_address("198.51.100.42"),
        destination_ip=ipaddress.ip_address("192.168.1.100"),
        protocol="tcp",
        packet_count=300,
        byte_count=15000,
        syn_count=280,
        ack_count=0,
        destination_ports=[443],
    )
    window = make_window([feature])
    events = detector.evaluate(node_id, window)

    assert len(events) == 1
    assert events[0].severity == DetectionSeverity.CRITICAL
    assert events[0].confidence_score >= 0.95


# ─── 2. PORT SCAN DETECTOR TESTS ───

def test_port_scan_detector_normal_ports_no_alert() -> None:
    detector = PortScanDetector(port_threshold=15)
    node_id = uuid.uuid4()
    feature = NetworkFeature(
        source_ip=ipaddress.ip_address("192.168.1.50"),
        destination_ip=ipaddress.ip_address("192.168.1.100"),
        protocol="tcp",
        packet_count=20,
        byte_count=1000,
        destination_ports=[80, 443],
    )
    window = make_window([feature])
    events = detector.evaluate(node_id, window)
    assert events == []


def test_port_scan_detector_triggers_medium_on_15_ports() -> None:
    detector = PortScanDetector(port_threshold=15)
    node_id = uuid.uuid4()
    ports = sorted(list(range(1000, 1016)))  # 16 ports
    feature = NetworkFeature(
        source_ip=ipaddress.ip_address("203.0.113.88"),
        destination_ip=ipaddress.ip_address("192.168.1.100"),
        protocol="tcp",
        packet_count=32,
        byte_count=2000,
        destination_ports=ports,
    )
    window = make_window([feature])
    events = detector.evaluate(node_id, window)

    assert len(events) == 1
    event = events[0]
    assert event.detector_name == "port_scan_detector"
    assert event.attacker_ip == "203.0.113.88"
    assert event.severity == DetectionSeverity.MEDIUM
    assert isinstance(event.details, NetworkAnomalyDetail)
    assert event.details.attack_type == "PORT_SCAN"
    assert len(event.details.targeted_ports) == 16


def test_port_scan_detector_triggers_high_on_30_ports_or_truncated() -> None:
    detector = PortScanDetector(port_threshold=15)
    node_id = uuid.uuid4()
    ports = sorted(list(range(2000, 2035)))  # 35 ports
    feature = NetworkFeature(
        source_ip=ipaddress.ip_address("203.0.113.99"),
        destination_ip=ipaddress.ip_address("192.168.1.100"),
        protocol="tcp",
        packet_count=70,
        byte_count=4000,
        destination_ports=ports,
        ports_truncated=True,
    )
    window = make_window([feature])
    events = detector.evaluate(node_id, window)

    assert len(events) == 1
    assert events[0].severity == DetectionSeverity.HIGH


# ─── 3. TRAFFIC SPIKE DETECTOR TESTS ───

def test_traffic_spike_detector_normal_no_alert() -> None:
    detector = TrafficSpikeDetector(
        packet_threshold=1000, byte_threshold=5_000_000, udp_threshold=300
    )
    node_id = uuid.uuid4()
    feature = NetworkFeature(
        source_ip=ipaddress.ip_address("192.168.1.50"),
        destination_ip=ipaddress.ip_address("192.168.1.100"),
        protocol="udp",
        packet_count=100,
        byte_count=20000,
        destination_ports=[53],
    )
    window = make_window([feature])
    events = detector.evaluate(node_id, window)
    assert events == []


def test_traffic_spike_detector_triggers_udp_flood() -> None:
    detector = TrafficSpikeDetector(
        packet_threshold=1000, byte_threshold=5_000_000, udp_threshold=300
    )
    node_id = uuid.uuid4()
    feature = NetworkFeature(
        source_ip=ipaddress.ip_address("203.0.113.77"),
        destination_ip=ipaddress.ip_address("192.168.1.100"),
        protocol="udp",
        packet_count=500,
        byte_count=150000,
        destination_ports=[53],
    )
    window = make_window([feature])
    events = detector.evaluate(node_id, window)

    assert len(events) == 1
    event = events[0]
    assert event.detector_name == "traffic_spike_detector"
    assert event.attacker_ip == "203.0.113.77"
    assert event.severity == DetectionSeverity.HIGH
    assert isinstance(event.details, NetworkAnomalyDetail)
    assert event.details.attack_type == "UDP_FLOOD"


def test_traffic_spike_detector_triggers_critical_on_high_volumetric_packets() -> None:
    detector = TrafficSpikeDetector(
        packet_threshold=1000, byte_threshold=5_000_000, udp_threshold=300
    )
    node_id = uuid.uuid4()
    feature = NetworkFeature(
        source_ip=ipaddress.ip_address("203.0.113.77"),
        destination_ip=ipaddress.ip_address("192.168.1.100"),
        protocol="tcp",
        packet_count=2500,
        byte_count=12_000_000,
        destination_ports=[80],
    )
    window = make_window([feature])
    events = detector.evaluate(node_id, window)

    assert len(events) == 1
    assert events[0].severity == DetectionSeverity.CRITICAL


# ─── 4. NETWORK ENGINE EVALUATE STATE & COOLDOWN TESTS ───

def test_network_engine_cooldown_and_multi_attacker_isolation() -> None:
    engine = DetectionEngine(cooldown_seconds=60)
    node_id = uuid.uuid4()
    now = datetime(2026, 11, 12, 10, 0, 0, tzinfo=UTC)

    # Window 1: Attacker A (203.0.113.10) sends SYN Flood
    feature_a = NetworkFeature(
        source_ip=ipaddress.ip_address("203.0.113.10"),
        destination_ip=ipaddress.ip_address("192.168.1.100"),
        protocol="tcp",
        packet_count=100,
        byte_count=5000,
        syn_count=80,
        ack_count=5,
        destination_ports=[80],
    )
    win1 = make_window([feature_a], start=now)
    events1, state1 = engine.evaluate_network_state(node_id, [win1], {})

    assert len(events1) == 1
    assert events1[0].attacker_ip == "203.0.113.10"
    assert events1[0].severity == DetectionSeverity.HIGH
    assert "network_alerts" in state1

    # Window 2: 10s later, Attacker A is still attacking (within 60s cooldown)
    # AND a NEW Attacker B (198.51.100.20) starts attacking!
    now2 = now + timedelta(seconds=10)
    feature_a2 = NetworkFeature(
        source_ip=ipaddress.ip_address("203.0.113.10"),
        destination_ip=ipaddress.ip_address("192.168.1.100"),
        protocol="tcp",
        packet_count=100,
        byte_count=5000,
        syn_count=85,
        ack_count=5,
        destination_ports=[80],
    )
    feature_b = NetworkFeature(
        source_ip=ipaddress.ip_address("198.51.100.20"),
        destination_ip=ipaddress.ip_address("192.168.1.100"),
        protocol="tcp",
        packet_count=150,
        byte_count=7000,
        syn_count=120,
        ack_count=0,
        destination_ports=[443],
    )
    win2 = make_window([feature_a2, feature_b], start=now2)
    events2, state2 = engine.evaluate_network_state(node_id, [win2], state1)

    # Attacker A should be suppressed by cooldown, but Attacker B MUST be alerted!
    assert len(events2) == 1
    assert events2[0].attacker_ip == "198.51.100.20"
    assert events2[0].severity == DetectionSeverity.CRITICAL


def test_network_engine_escalation_bypasses_cooldown() -> None:
    engine = DetectionEngine(cooldown_seconds=60)
    node_id = uuid.uuid4()
    now = datetime(2026, 11, 12, 10, 0, 0, tzinfo=UTC)

    # Window 1: Attacker sends HIGH severity SYN Flood
    feature_high = NetworkFeature(
        source_ip=ipaddress.ip_address("203.0.113.10"),
        destination_ip=ipaddress.ip_address("192.168.1.100"),
        protocol="tcp",
        packet_count=100,
        byte_count=5000,
        syn_count=70,
        ack_count=10,
        destination_ports=[80],
    )
    win1 = make_window([feature_high], start=now)
    events1, state1 = engine.evaluate_network_state(node_id, [win1], {})
    assert len(events1) == 1
    assert events1[0].severity == DetectionSeverity.HIGH

    # Window 2: 5s later, Attacker escalates to CRITICAL (250 SYN)
    now2 = now + timedelta(seconds=5)
    feature_crit = NetworkFeature(
        source_ip=ipaddress.ip_address("203.0.113.10"),
        destination_ip=ipaddress.ip_address("192.168.1.100"),
        protocol="tcp",
        packet_count=300,
        byte_count=15000,
        syn_count=260,
        ack_count=0,
        destination_ports=[80],
    )
    win2 = make_window([feature_crit], start=now2)
    events2, state2 = engine.evaluate_network_state(node_id, [win2], state1)

    # Escalation from HIGH to CRITICAL must bypass cooldown!
    assert len(events2) == 1
    assert events2[0].severity == DetectionSeverity.CRITICAL
