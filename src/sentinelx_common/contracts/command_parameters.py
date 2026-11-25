"""Bounded, canonical command parameters shared by Controller and Agent."""

import ipaddress
import re
from typing import Any

SUPPORTED_ACTIONS = frozenset(
    {
        "BLOCK_IP_NFTABLES",
        "UNBLOCK_IP_NFTABLES",
        "ALERT_ONLY",
        "RESTART_SERVICE",
        "CLEAR_OS_CACHE",
        "ADAPTIVE",
    }
)
PROTECTED_SYSTEM_SERVICES = frozenset(
    {
        "systemd",
        "init",
        "sshd",
        "ssh",
        "sentinelx-agent",
        "docker",
        "dockerd",
        "containerd",
        "postgres",
        "postgresql",
        "db",
    }
)
MAX_BLOCK_SECONDS = 86400


def is_protected_system_service(service_name: str) -> bool:
    """Return True if service_name refers to a core OS or control-plane daemon."""
    clean = service_name.strip().lower()
    if clean.endswith(".service"):
        clean = clean[:-8]
    return clean in PROTECTED_SYSTEM_SERVICES


def normalize_command(
    action_type: str,
    target_ip: str | None,
    payload: dict[str, Any],
    *,
    max_duration: int = MAX_BLOCK_SECONDS,
) -> tuple[str | None, dict[str, Any]]:
    """Reject ambiguous/unsafe parameters; normalize the legacy duration alias."""
    if action_type not in SUPPORTED_ACTIONS:
        raise ValueError(f"Action {action_type} is not supported by a CORE executor")
    normalized = dict(payload)
    if action_type == "ALERT_ONLY":
        return None, normalized
    if action_type == "CLEAR_OS_CACHE":
        return "os-cache", normalized
    if action_type == "ADAPTIVE":
        raw_svc = normalized.get("service_name") or normalized.get("target")
        if isinstance(raw_svc, str) and raw_svc.strip() and raw_svc.strip() != "adaptive":
            clean_name = raw_svc.strip()
            if not re.fullmatch(r"[a-zA-Z0-9_\-\.]{1,64}", clean_name):
                raise ValueError(f"Invalid service identifier: {clean_name}")
            normalized["service_name"] = clean_name
            normalized["target"] = clean_name
            return clean_name, normalized
        return (target_ip or "adaptive"), normalized
    if action_type == "RESTART_SERVICE":
        service_name = normalized.get("service_name") or normalized.get("target") or target_ip
        if not service_name or not isinstance(service_name, str):
            raise ValueError("Service name is required for RESTART_SERVICE")
        clean_name = service_name.strip()
        if not re.fullmatch(r"[a-zA-Z0-9_\-\.]{1,64}", clean_name):
            raise ValueError(f"Invalid service identifier: {clean_name}")
        normalized["service_name"] = clean_name
        normalized["target"] = clean_name
        return clean_name, normalized

    if target_ip is None:
        raise ValueError("Target IP is required")
    try:
        target = str(ipaddress.ip_address(target_ip))
    except ValueError as error:
        raise ValueError("Invalid target IP address") from error
    if action_type == "BLOCK_IP_NFTABLES":
        duration = normalized.get(
            "duration_seconds", normalized.get("block_duration_seconds", 1800)
        )
        if "duration_seconds" in normalized and "block_duration_seconds" in normalized:
            if normalized["duration_seconds"] != normalized["block_duration_seconds"]:
                raise ValueError("Conflicting duration fields")
        if isinstance(duration, bool) or not isinstance(duration, int):
            raise ValueError("duration_seconds must be an integer")
        if not 1 <= duration <= max_duration:
            raise ValueError(f"duration_seconds must be between 1 and {max_duration}")
        normalized.pop("block_duration_seconds", None)
        normalized["duration_seconds"] = duration
    return target, normalized
