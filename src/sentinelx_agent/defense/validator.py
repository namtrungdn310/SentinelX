"""Local safety validator enforcing dual-layer defense guardrails on the Agent host."""

import ipaddress
import logging
import socket
from urllib.parse import urlsplit

import psutil

from sentinelx_common.contracts.defense import AgentCommandContract
from sentinelx_common.contracts.policy import PolicyActionType

logger = logging.getLogger("sentinelx_agent.defense.validator")


class LocalSafetyValidator:
    """Validates that incoming controller commands do not target protected or local addresses."""

    def __init__(self, protected_cidrs: list[str] | None = None) -> None:
        self._loopback_networks = [
            ipaddress.ip_network("127.0.0.0/8"),
            ipaddress.ip_network("::1/128"),
        ]
        self._custom_protected: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        if protected_cidrs:
            for cidr in protected_cidrs:
                try:
                    self._custom_protected.append(ipaddress.ip_network(cidr, strict=False))
                except ValueError:
                    logger.warning("Invalid protected CIDR: %s", cidr)

    def _get_local_ips(self) -> set[str]:
        """Collect all local IP addresses bound to network interfaces on this host."""
        ips: set[str] = {"127.0.0.1", "::1"}
        try:
            for _iface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family in (socket.AF_INET, socket.AF_INET6):
                        clean_ip = addr.address.split("%")[0]
                        ips.add(clean_ip)
        except Exception as err:
            logger.debug("Failed scanning local interfaces: %s", err)
        return ips

    def _extract_controller_host(self, controller_url: str) -> str | None:
        try:
            parsed = urlsplit(controller_url)
            return parsed.hostname
        except Exception:
            return None

    def validate(
        self,
        command: AgentCommandContract,
        controller_url: str,
    ) -> tuple[bool, str | None]:
        """Validate command safety. Returns (is_valid, rejection_reason)."""
        # 1. Action type validation
        allowed_actions = {a.value for a in PolicyActionType}
        if command.action_type not in allowed_actions:
            return False, f"Action type '{command.action_type}' is not supported"

        # 2. Target IP validation (if command specifies a target IP)
        if command.target_ip:
            try:
                target_obj = ipaddress.ip_address(command.target_ip)
            except ValueError:
                return False, f"Invalid target IP address: {command.target_ip}"

            # Check loopback
            if any(target_obj in net for net in self._loopback_networks):
                return False, f"Target IP {command.target_ip} is a loopback address"

            # Check Controller IP / Hostname
            ctrl_host = self._extract_controller_host(controller_url)
            if ctrl_host:
                if str(target_obj) == ctrl_host:
                    return False, f"Target IP {command.target_ip} matches Controller hostname"
                try:
                    ctrl_obj = ipaddress.ip_address(ctrl_host)
                    if target_obj == ctrl_obj:
                        return False, f"Target IP {command.target_ip} matches Controller IP"
                except ValueError:
                    pass

            # Check local host interfaces (cannot block own node)
            local_ips = self._get_local_ips()
            if str(target_obj) in local_ips:
                return (
                    False,
                    f"Target IP {command.target_ip} matches a local interface on this node",
                )

            # Check custom protected networks
            for net in self._custom_protected:
                if target_obj in net:
                    return False, f"Target IP {command.target_ip} is in protected network {net}"

        return True, None
