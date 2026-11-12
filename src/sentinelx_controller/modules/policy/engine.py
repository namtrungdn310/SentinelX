"""Policy evaluation engine with safety guardrails and cooldown tracking."""

import ipaddress
import logging
from datetime import UTC, datetime

from sentinelx_common.contracts.detection import DetectionEventContract
from sentinelx_common.contracts.policy import (
    PolicyActionType,
    PolicyEvaluationResult,
    PolicyEvaluationStatus,
)
from sentinelx_controller.modules.policy.models import DefensePolicyModel, IPWhitelistModel

logger = logging.getLogger(__name__)


class PolicyEngine:
    """Core engine evaluating detection events against policies and safety rules."""

    def __init__(self) -> None:
        # Lưu thời điểm thực thi hành động: key -> datetime
        # Key: f"{project_id}_{action_type}_{target}"
        self._cooldown_tracker: dict[str, datetime] = {}
        # Các dải IP mạng loopback bảo vệ tuyệt đối không bao giờ được phép chặn
        self._loopback_networks = [
            ipaddress.ip_network("127.0.0.0/8"),
            ipaddress.ip_network("::1/128"),
        ]

    def clear_state(self) -> None:
        """Reset internal cooldown tracking state (useful for tests)."""
        self._cooldown_tracker.clear()

    def evaluate(
        self,
        event: DetectionEventContract,
        policies: list[DefensePolicyModel],
        whitelists: list[IPWhitelistModel],
        controller_ip: str | None = None,
    ) -> PolicyEvaluationResult:
        """Thẩm định một detection event và đưa ra quyết định hành động."""
        now = datetime.now(UTC)

        # ─── BƯỚC 1: Kiểm tra IP Whitelist (Nếu có IP kẻ tấn công) ───
        if event.attacker_ip:
            try:
                ip_obj = ipaddress.ip_address(event.attacker_ip)
            except ValueError:
                return PolicyEvaluationResult(
                    authorized=False,
                    status=PolicyEvaluationStatus.DENIED_WHITELIST,
                    reason=f"Địa chỉ IP không hợp lệ: {event.attacker_ip}",
                )

            # 1.1. Bảo vệ Loopback
            if any(ip_obj in net for net in self._loopback_networks):
                logger.warning("BLOCK DENIED: IP %s thuộc dải loopback", event.attacker_ip)
                return PolicyEvaluationResult(
                    authorized=False,
                    status=PolicyEvaluationStatus.DENIED_WHITELIST,
                    target=event.attacker_ip,
                    reason="CẤM CHẶN: Địa chỉ thuộc dải loopback nội bộ hệ thống",
                )

            # 1.2. Bảo vệ Controller IP
            if controller_ip and event.attacker_ip == controller_ip:
                logger.warning("BLOCK DENIED: IP %s là địa chỉ Controller", event.attacker_ip)
                return PolicyEvaluationResult(
                    authorized=False,
                    status=PolicyEvaluationStatus.DENIED_WHITELIST,
                    target=event.attacker_ip,
                    reason="CẤM CHẶN: Địa chỉ trùng với địa chỉ máy chủ Controller",
                )

            # 1.3. Bảo vệ IP nằm trong danh sách Whitelist của dự án
            for item in whitelists:
                try:
                    wl_net = ipaddress.ip_network(item.ip_or_cidr, strict=False)
                    if ip_obj in wl_net:
                        logger.warning(
                            "BLOCK DENIED: IP %s nằm trong whitelist %s (%s)",
                            event.attacker_ip,
                            item.ip_or_cidr,
                            item.description,
                        )
                        desc = item.description or "whitelist"
                        return PolicyEvaluationResult(
                            authorized=False,
                            status=PolicyEvaluationStatus.DENIED_WHITELIST,
                            target=event.attacker_ip,
                            reason=f"IP nằm trong danh sách an toàn: {item.ip_or_cidr} ({desc})",
                        )
                except ValueError:
                    logger.error("Dải whitelist không hợp lệ trong database: %s", item.ip_or_cidr)

        # ─── BƯỚC 2: Khớp Quy tắc (Rule Matching) ───
        matched_policy: DefensePolicyModel | None = None
        for p in policies:
            if p.event_type == event.detector_name:
                if not p.enabled:
                    return PolicyEvaluationResult(
                        authorized=False,
                        status=PolicyEvaluationStatus.DENIED_DISABLED,
                        policy_id=str(p.id),
                        reason=f"Chính sách '{p.name}' đang bị vô hiệu hóa (disabled)",
                    )
                matched_policy = p
                break

        if matched_policy is None:
            return PolicyEvaluationResult(
                authorized=False,
                status=PolicyEvaluationStatus.NO_POLICY_MATCH,
                reason=(
                    f"Không tìm thấy chính sách nào được cấu hình cho sự kiện "
                    f"'{event.detector_name}'"
                ),
            )

        # Xác định mục tiêu can thiệp (Target)
        action_type = PolicyActionType(matched_policy.action_type)
        target = (
            event.attacker_ip
            or matched_policy.target_params.get("service_name")
            or matched_policy.target_params.get("process_name")
            or str(event.node_id)
        )

        block_duration = matched_policy.block_duration_seconds or 0
        cooldown = matched_policy.cooldown_seconds or 0

        # ─── BƯỚC 3 & 4: Kiểm tra Chống trùng lặp & Cooldown ───
        cooldown_key = f"{matched_policy.project_id}_{action_type.value}_{target}"
        if cooldown_key in self._cooldown_tracker:
            last_run = self._cooldown_tracker[cooldown_key]
            elapsed = (now - last_run).total_seconds()

            # Đối với hành động duy trì trạng thái như BLOCK_IP / RATE_LIMIT:
            if action_type in (
                PolicyActionType.BLOCK_IP_NFTABLES,
                PolicyActionType.RATE_LIMIT,
            ):
                if elapsed < block_duration:
                    return PolicyEvaluationResult(
                        authorized=False,
                        status=PolicyEvaluationStatus.DENIED_DUPLICATE,
                        action_type=action_type,
                        target=target,
                        duration_seconds=block_duration,
                        policy_id=str(matched_policy.id),
                        reason=(
                            f"Mục tiêu '{target}' đang có hiệu lực thi hành hành động "
                            f"{action_type.value}"
                        ),
                    )

            # Đối với hành động tức thời hoặc thời gian hạ nhiệt chung:
            if elapsed < cooldown:
                remaining = int(cooldown - elapsed)
                return PolicyEvaluationResult(
                    authorized=False,
                    status=PolicyEvaluationStatus.DENIED_COOLDOWN,
                    action_type=action_type,
                    target=target,
                    policy_id=str(matched_policy.id),
                    reason=f"Chính sách đang trong thời gian hạ nhiệt, vui lòng chờ {remaining}s",
                )

        # Ghi nhận mốc thời gian kích hoạt
        self._cooldown_tracker[cooldown_key] = now

        # ─── BƯỚC 5: Phê duyệt Hành động ───
        is_auto = (
            bool(matched_policy.is_auto_execute)
            if matched_policy.is_auto_execute is not None
            else True
        )
        return PolicyEvaluationResult(
            authorized=True,
            status=PolicyEvaluationStatus.ACTION_AUTHORIZED,
            action_type=action_type,
            target=target,
            duration_seconds=block_duration,
            policy_id=str(matched_policy.id),
            is_auto_execute=is_auto,
            reason=f"Phê duyệt {action_type.value} theo chính sách '{matched_policy.name}'",
        )
