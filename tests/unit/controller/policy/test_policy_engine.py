"""Unit tests for PolicyEngine guardrails and evaluation logic."""

import uuid
from datetime import UTC, datetime

from sentinelx_common.contracts.detection import (
    DetectionEventContract,
    DetectionSeverity,
    ResourceAnomalyDetail,
)
from sentinelx_common.contracts.policy import (
    PolicyActionType,
    PolicyEvaluationStatus,
)
from sentinelx_controller.modules.policy.engine import PolicyEngine
from sentinelx_controller.modules.policy.models import DefensePolicyModel, IPWhitelistModel


def make_event(
    detector_name: str = "cpu_threshold_detector",
    attacker_ip: str | None = None,
    severity: DetectionSeverity = DetectionSeverity.HIGH,
) -> DetectionEventContract:
    return DetectionEventContract(
        node_id=str(uuid.uuid4()),
        detector_name=detector_name,
        severity=severity,
        attacker_ip=attacker_ip,
        confidence_score=0.95,
        details=ResourceAnomalyDetail(
            metric_name="cpu_percent",
            current_value=96.0,
            threshold_value=80.0,
            window_duration_seconds=15,
            consecutive_samples=3,
        ),
        detected_at=datetime.now(UTC),
    )


def test_whitelist_blocks_loopback_and_controller_ip() -> None:
    engine = PolicyEngine()

    event = make_event(attacker_ip="127.0.0.1")
    res = engine.evaluate(event, policies=[], whitelists=[])
    assert res.status == PolicyEvaluationStatus.DENIED_WHITELIST
    assert "loopback" in res.reason

    event_ipv6 = make_event(attacker_ip="::1")
    res_ipv6 = engine.evaluate(event_ipv6, policies=[], whitelists=[])
    assert res_ipv6.status == PolicyEvaluationStatus.DENIED_WHITELIST

    event_ctrl = make_event(attacker_ip="10.0.0.2")
    res_ctrl = engine.evaluate(event_ctrl, policies=[], whitelists=[], controller_ip="10.0.0.2")
    assert res_ctrl.status == PolicyEvaluationStatus.DENIED_WHITELIST
    assert "Controller" in res_ctrl.reason


def test_project_ip_whitelist_protects_subnet() -> None:
    engine = PolicyEngine()
    project_id = uuid.uuid4()
    whitelist = [
        IPWhitelistModel(
            id=uuid.uuid4(),
            project_id=project_id,
            ip_or_cidr="192.168.1.0/24",
            description="Office LAN",
        ),
    ]

    event = make_event(attacker_ip="192.168.1.45")
    res = engine.evaluate(event, policies=[], whitelists=whitelist)
    assert res.status == PolicyEvaluationStatus.DENIED_WHITELIST
    assert "192.168.1.0/24" in res.reason


def test_no_matching_policy_or_disabled() -> None:
    engine = PolicyEngine()
    project_id = uuid.uuid4()

    event = make_event(detector_name="unknown_detector")
    res = engine.evaluate(event, policies=[], whitelists=[])
    assert res.status == PolicyEvaluationStatus.NO_POLICY_MATCH

    disabled_policy = DefensePolicyModel(
        id=uuid.uuid4(),
        project_id=project_id,
        name="Disabled Policy",
        event_type="cpu_threshold_detector",
        action_type="RESTART_SERVICE",
        target_params={"service_name": "backend"},
        enabled=False,
    )
    event_cpu = make_event(detector_name="cpu_threshold_detector")
    res_disabled = engine.evaluate(event_cpu, policies=[disabled_policy], whitelists=[])
    assert res_disabled.status == PolicyEvaluationStatus.DENIED_DISABLED


def test_cooldown_prevents_rapid_service_restart() -> None:
    engine = PolicyEngine()
    project_id = uuid.uuid4()
    policy = DefensePolicyModel(
        id=uuid.uuid4(),
        project_id=project_id,
        name="Auto Restart on Overload",
        event_type="cpu_threshold_detector",
        action_type="RESTART_SERVICE",
        target_params={"service_name": "nginx"},
        cooldown_seconds=300,
        enabled=True,
    )

    event = make_event(detector_name="cpu_threshold_detector")

    # First execution should succeed
    res1 = engine.evaluate(event, policies=[policy], whitelists=[])
    assert res1.authorized is True
    assert res1.status == PolicyEvaluationStatus.ACTION_AUTHORIZED
    assert res1.action_type == PolicyActionType.RESTART_SERVICE
    assert res1.target == "nginx"

    # Immediate second call should be denied by cooldown
    res2 = engine.evaluate(event, policies=[policy], whitelists=[])
    assert res2.authorized is False
    assert res2.status == PolicyEvaluationStatus.DENIED_COOLDOWN
    assert "hạ nhiệt" in res2.reason


def test_duplicate_prevention_for_ip_blocking() -> None:
    engine = PolicyEngine()
    project_id = uuid.uuid4()
    policy = DefensePolicyModel(
        id=uuid.uuid4(),
        project_id=project_id,
        name="Block Port Scanner",
        event_type="port_scan_detector",
        action_type="BLOCK_IP_NFTABLES",
        block_duration_seconds=1800,
        cooldown_seconds=60,
        enabled=True,
    )

    event = make_event(detector_name="port_scan_detector", attacker_ip="203.0.113.88")

    # First call: approved
    res1 = engine.evaluate(event, policies=[policy], whitelists=[])
    assert res1.authorized is True
    assert res1.status == PolicyEvaluationStatus.ACTION_AUTHORIZED
    assert res1.action_type == PolicyActionType.BLOCK_IP_NFTABLES
    assert res1.target == "203.0.113.88"

    # Immediate second call: denied by duplicate (active block duration)
    res2 = engine.evaluate(event, policies=[policy], whitelists=[])
    assert res2.authorized is False
    assert res2.status == PolicyEvaluationStatus.DENIED_DUPLICATE
    assert "đang có hiệu lực" in res2.reason
