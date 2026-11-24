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
            extra_context={"direction": "inbound"},
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
        action_type="ALERT_ONLY",
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
        action_type="ALERT_ONLY",
        target_params={"service_name": "nginx"},
        cooldown_seconds=300,
        enabled=True,
    )

    event = make_event(detector_name="cpu_threshold_detector")

    # First execution should succeed
    res1 = engine.evaluate(event, policies=[policy], whitelists=[])
    assert res1.authorized is True
    assert res1.status == PolicyEvaluationStatus.ACTION_AUTHORIZED
    assert res1.action_type == PolicyActionType.ALERT_ONLY
    assert res1.target == event.node_id

    # Immediate second call should be denied by cooldown
    res2 = engine.evaluate(
        event, policies=[policy], whitelists=[], last_authorized_at=datetime.now(UTC)
    )
    assert res2.authorized is False
    assert res2.status == PolicyEvaluationStatus.DENIED_COOLDOWN
    assert "cooldown" in res2.reason


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
    res2 = engine.evaluate(
        event, policies=[policy], whitelists=[], last_authorized_at=datetime.now(UTC)
    )
    assert res2.authorized is False
    assert res2.status == PolicyEvaluationStatus.DENIED_DUPLICATE
    assert "recently authorized" in res2.reason


def _resource_event(
    detector_name: str,
    *,
    current_value: float,
    process_name: str | None = None,
    process_percent: float | None = None,
) -> DetectionEventContract:
    metric_name = (
        "memory_percent" if detector_name == "memory_exhaustion_detector" else "cpu_percent"
    )
    extra: dict[str, object] = {}
    if process_name is not None:
        extra["process_name"] = process_name
    if process_percent is not None:
        extra["process_percent"] = process_percent
        if metric_name == "memory_percent":
            extra["process_memory_percent"] = process_percent
        else:
            extra["process_cpu_percent"] = process_percent
    return DetectionEventContract(
        node_id=str(uuid.uuid4()),
        detector_name=detector_name,
        severity=DetectionSeverity.HIGH,
        attacker_ip=None,
        confidence_score=0.92,
        details=ResourceAnomalyDetail(
            metric_name=metric_name,
            current_value=current_value,
            threshold_value=85.0,
            window_duration_seconds=10,
            consecutive_samples=3,
            extra_context=extra,
        ),
        detected_at=datetime.now(UTC),
    )


def test_adaptive_memory_requires_40_percent_dominance_else_clears_os_cache() -> None:
    engine = PolicyEngine()
    policy = DefensePolicyModel(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        name="Quá tải RAM",
        event_type="memory_exhaustion_detector",
        action_type="ADAPTIVE",
        cooldown_seconds=180,
        block_duration_seconds=0,
        enabled=True,
    )

    # >= 40% share (60 / 90 = 66.7%) -> RESTART_SERVICE
    dominant_ev = _resource_event(
        "memory_exhaustion_detector",
        current_value=90.0,
        process_name="nginx",
        process_percent=60.0,
    )
    res_dominant = engine.evaluate(dominant_ev, policies=[policy], whitelists=[])
    assert res_dominant.authorized is True
    assert res_dominant.action_type == PolicyActionType.RESTART_SERVICE
    assert res_dominant.target == "nginx"

    # < 40% share (20 / 90 = 22.2%) -> CLEAR_OS_CACHE fallback
    distributed_ev = _resource_event(
        "memory_exhaustion_detector",
        current_value=90.0,
        process_name="worker",
        process_percent=20.0,
    )
    res_distributed = engine.evaluate(distributed_ev, policies=[policy], whitelists=[])
    assert res_distributed.authorized is True
    assert res_distributed.action_type == PolicyActionType.CLEAR_OS_CACHE
    assert res_distributed.target == "os-cache"

    # Protected system service even with high usage -> safe fallback to CLEAR_OS_CACHE
    protected_ev = _resource_event(
        "memory_exhaustion_detector",
        current_value=92.0,
        process_name="postgres.service",
        process_percent=70.0,
    )
    res_protected = engine.evaluate(protected_ev, policies=[policy], whitelists=[])
    assert res_protected.authorized is True
    assert res_protected.action_type == PolicyActionType.CLEAR_OS_CACHE


def test_adaptive_cpu_requires_40_percent_dominance_else_alert_only() -> None:
    engine = PolicyEngine()
    policy = DefensePolicyModel(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        name="Quá tải CPU",
        event_type="cpu_threshold_detector",
        action_type="ADAPTIVE",
        cooldown_seconds=300,
        block_duration_seconds=0,
        enabled=True,
    )

    dominant_ev = _resource_event(
        "cpu_threshold_detector",
        current_value=90.0,
        process_name="celery-worker",
        process_percent=50.0,
    )
    res_dominant = engine.evaluate(dominant_ev, policies=[policy], whitelists=[])
    assert res_dominant.authorized is True
    assert res_dominant.action_type == PolicyActionType.RESTART_SERVICE
    assert res_dominant.target == "celery-worker"

    low_share_ev = _resource_event(
        "cpu_threshold_detector",
        current_value=90.0,
        process_name="cron",
        process_percent=15.0,
    )
    res_low = engine.evaluate(low_share_ev, policies=[policy], whitelists=[])
    assert res_low.authorized is True
    assert res_low.action_type == PolicyActionType.ALERT_ONLY


def test_explicit_restart_rejects_missing_or_protected_service() -> None:
    engine = PolicyEngine()
    policy = DefensePolicyModel(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        name="Restart CPU",
        event_type="cpu_threshold_detector",
        action_type="RESTART_SERVICE",
        target_params={},
        enabled=True,
    )

    no_proc_ev = _resource_event("cpu_threshold_detector", current_value=92.0)
    res_missing = engine.evaluate(no_proc_ev, policies=[policy], whitelists=[])
    assert res_missing.authorized is False
    assert res_missing.status == PolicyEvaluationStatus.NO_POLICY_MATCH

    protected_ev = _resource_event(
        "cpu_threshold_detector",
        current_value=92.0,
        process_name="sshd",
        process_percent=75.0,
    )
    res_protected = engine.evaluate(protected_ev, policies=[policy], whitelists=[])
    assert res_protected.authorized is False
    assert res_protected.status == PolicyEvaluationStatus.NO_POLICY_MATCH
