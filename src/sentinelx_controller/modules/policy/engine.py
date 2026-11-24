"""Pure policy evaluation; durable cooldown ownership belongs to the repository."""

import ipaddress
from datetime import UTC, datetime
from typing import Literal

from sentinelx_common.contracts.command_parameters import (
    SUPPORTED_ACTIONS,
    is_protected_system_service,
)
from sentinelx_common.contracts.detection import (
    DetectionEventContract,
    ResourceAnomalyDetail,
)
from sentinelx_common.contracts.policy import (
    PolicyActionType,
    PolicyEvaluationResult,
    PolicyEvaluationStatus,
)
from sentinelx_common.utils.time import ensure_utc
from sentinelx_controller.modules.policy.models import DefensePolicyModel, IPWhitelistModel

DOMINANT_PROCESS_SHARE_THRESHOLD = 0.40


def _resolve_dominant_process(
    event: DetectionEventContract,
    metric_kind: Literal["cpu", "memory"],
) -> str | None:
    """Return process_name only if it is safe to restart and dominates the overloaded metric."""
    details = event.details
    extra = details.extra_context or {}
    raw_name = extra.get("process_name")
    if not isinstance(raw_name, str) or not raw_name.strip():
        return None
    process_name = raw_name.strip()
    if is_protected_system_service(process_name):
        return None

    specific_key = "process_memory_percent" if metric_kind == "memory" else "process_cpu_percent"
    proc_pct = extra.get(specific_key)
    if proc_pct is None:
        proc_pct = extra.get("process_percent")

    if isinstance(details, ResourceAnomalyDetail) and isinstance(proc_pct, int | float):
        if details.current_value > 0:
            share = float(proc_pct) / float(details.current_value)
            if share < DOMINANT_PROCESS_SHARE_THRESHOLD:
                return None

    return process_name


class PolicyEngine:
    """Evaluate a snapshot without mutating shared process state."""

    def clear_state(self) -> None:
        """Compatibility hook: the evaluator owns no mutable cooldown state."""

    def evaluate(
        self,
        event: DetectionEventContract,
        policies: list[DefensePolicyModel],
        whitelists: list[IPWhitelistModel],
        controller_ip: str | None = None,
        *,
        last_authorized_at: datetime | None = None,
        protected_cidrs: list[str] | None = None,
        now: datetime | None = None,
    ) -> PolicyEvaluationResult:
        current = now or datetime.now(UTC)
        if event.attacker_ip:
            try:
                target_ip = ipaddress.ip_address(event.attacker_ip)
            except ValueError:
                return PolicyEvaluationResult(
                    authorized=False,
                    status=PolicyEvaluationStatus.DENIED_WHITELIST,
                    reason="Invalid target address",
                )
            protected = [entry.ip_or_cidr for entry in whitelists] + (protected_cidrs or [])
            if controller_ip:
                protected.append(controller_ip)
            forbidden = (
                target_ip.is_loopback
                or target_ip.is_unspecified
                or target_ip.is_multicast
                or target_ip.is_link_local
            )
            rejection = "Protected loopback/non-unicast address"
            for cidr in protected:
                try:
                    if target_ip in ipaddress.ip_network(cidr, strict=False):
                        forbidden = True
                        rejection = f"Protected Controller/whitelist network: {cidr}"
                except ValueError:
                    # Invalid protection configuration must never silently permit a block.
                    forbidden = True
                    rejection = "Invalid infrastructure protection configuration"
            if forbidden:
                return PolicyEvaluationResult(
                    authorized=False,
                    status=PolicyEvaluationStatus.DENIED_WHITELIST,
                    target=str(target_ip),
                    reason=rejection,
                )
        matching = [p for p in policies if p.event_type == event.detector_name]
        policy = next((p for p in matching if p.enabled), None)
        if policy is None:
            return PolicyEvaluationResult(
                authorized=False,
                status=(
                    PolicyEvaluationStatus.DENIED_DISABLED
                    if matching
                    else PolicyEvaluationStatus.NO_POLICY_MATCH
                ),
                reason="No enabled matching policy",
            )
        if (
            policy.action_type not in SUPPORTED_ACTIONS
            or policy.action_type == "UNBLOCK_IP_NFTABLES"
        ):
            return PolicyEvaluationResult(
                authorized=False,
                status=PolicyEvaluationStatus.NO_POLICY_MATCH,
                policy_id=str(policy.id),
                reason="Action has no supported automatic CORE executor",
            )
        if policy.action_type == "BLOCK_IP_NFTABLES" and not event.attacker_ip:
            return PolicyEvaluationResult(
                authorized=False,
                status=PolicyEvaluationStatus.NO_POLICY_MATCH,
                policy_id=str(policy.id),
                reason="Firewall action requires an observed attacker IP",
            )
        if policy.action_type == "BLOCK_IP_NFTABLES":
            context = event.details.extra_context
            if (
                context.get("direction") != "inbound"
                or context.get("eligible_for_automatic_defense") is False
            ):
                return PolicyEvaluationResult(
                    authorized=False,
                    status=PolicyEvaluationStatus.NO_POLICY_MATCH,
                    policy_id=str(policy.id),
                    reason="Automatic blocking requires eligible inbound evidence",
                )
        action = PolicyActionType(policy.action_type)
        if action == PolicyActionType.ADAPTIVE:
            if event.detector_name == "memory_exhaustion_detector":
                dominant = _resolve_dominant_process(event, "memory")
                if dominant is not None:
                    action = PolicyActionType.RESTART_SERVICE
                    target = dominant
                else:
                    action = PolicyActionType.CLEAR_OS_CACHE
                    target = "os-cache"
            elif event.detector_name == "cpu_threshold_detector":
                dominant = _resolve_dominant_process(event, "cpu")
                if dominant is not None:
                    action = PolicyActionType.RESTART_SERVICE
                    target = dominant
                else:
                    action = PolicyActionType.ALERT_ONLY
                    target = str(event.node_id)
            elif event.detector_name in (
                "syn_flood_detector",
                "port_scan_detector",
                "traffic_spike_detector",
            ):
                context = event.details.extra_context
                if (
                    event.attacker_ip
                    and context.get("direction") == "inbound"
                    and context.get("eligible_for_automatic_defense") is not False
                ):
                    action = PolicyActionType.BLOCK_IP_NFTABLES
                    target = event.attacker_ip
                else:
                    action = PolicyActionType.ALERT_ONLY
                    target = str(event.node_id)
            else:
                action = PolicyActionType.ALERT_ONLY
                target = str(event.node_id)
        elif action == PolicyActionType.RESTART_SERVICE:
            metric_kind: Literal["cpu", "memory"] = (
                "memory" if event.detector_name == "memory_exhaustion_detector" else "cpu"
            )
            dominant = _resolve_dominant_process(event, metric_kind)
            configured_target = str(
                policy.target_params.get("service_name")
                or policy.target_params.get("target")
                or ""
            ).strip()
            resolved = dominant or configured_target
            if not resolved:
                return PolicyEvaluationResult(
                    authorized=False,
                    status=PolicyEvaluationStatus.NO_POLICY_MATCH,
                    policy_id=str(policy.id),
                    reason="Service restart requires an identified dominant or configured service",
                )
            if is_protected_system_service(resolved):
                return PolicyEvaluationResult(
                    authorized=False,
                    status=PolicyEvaluationStatus.NO_POLICY_MATCH,
                    policy_id=str(policy.id),
                    reason=f"Target service '{resolved}' is a protected system service",
                )
            target = resolved
        elif action == PolicyActionType.CLEAR_OS_CACHE:
            target = "os-cache"
        else:
            target = event.attacker_ip or str(event.node_id)
        duration = policy.block_duration_seconds or 0
        if action == PolicyActionType.BLOCK_IP_NFTABLES and not 1 <= duration <= 86400:
            return PolicyEvaluationResult(
                authorized=False,
                status=PolicyEvaluationStatus.NO_POLICY_MATCH,
                policy_id=str(policy.id),
                reason="Unsafe block duration",
            )
        if last_authorized_at is not None:
            elapsed = (current - ensure_utc(last_authorized_at)).total_seconds()
            if action == PolicyActionType.BLOCK_IP_NFTABLES and elapsed < duration:
                return PolicyEvaluationResult(
                    authorized=False,
                    status=PolicyEvaluationStatus.DENIED_DUPLICATE,
                    policy_id=str(policy.id),
                    action_type=action,
                    target=target,
                    duration_seconds=duration,
                    reason="An equivalent block was recently authorized",
                )
            if elapsed < (policy.cooldown_seconds or 0):
                return PolicyEvaluationResult(
                    authorized=False,
                    status=PolicyEvaluationStatus.DENIED_COOLDOWN,
                    policy_id=str(policy.id),
                    action_type=action,
                    target=target,
                    reason="Policy cooldown is active",
                )
        return PolicyEvaluationResult(
            authorized=True,
            status=PolicyEvaluationStatus.ACTION_AUTHORIZED,
            policy_id=str(policy.id),
            action_type=action,
            target=target,
            duration_seconds=duration,
            is_auto_execute=bool(policy.is_auto_execute),
            reason=f"Authorized by policy '{policy.name}'",
        )
