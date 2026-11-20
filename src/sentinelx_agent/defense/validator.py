"""Local safety validator enforcing dual-layer defense guardrails on the Agent host."""

import ipaddress
import logging
import socket
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import psutil

from sentinelx_common.contracts.command_parameters import normalize_command
from sentinelx_common.contracts.defense import AgentCommandContract
from sentinelx_common.contracts.policy import PolicyActionType

logger = logging.getLogger("sentinelx_agent.defense.validator")


class LocalSafetyValidator:
    """Validates that incoming controller commands do not target protected or local addresses."""

    def __init__(
        self, protected_cidrs: list[str] | None = None, max_block_seconds: int = 86400
    ) -> None:
        self._max_block_seconds = max_block_seconds
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
                    raise ValueError("Invalid protected CIDR configuration") from None

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
            raise RuntimeError("Cannot inspect local interface protection") from err
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
        now = datetime.now(UTC)
        created = (
            command.created_at.replace(tzinfo=UTC)
            if command.created_at.tzinfo is None
            else command.created_at
        )
        if command.expires_at <= now or created > now + timedelta(seconds=30):
            return False, "Command expired or creation timestamp is in the future"
        if (command.expires_at - created).total_seconds() > 3600:
            return False, "Command lifetime exceeds local safety limit"
        try:
            normalize_command(
                command.action_type,
                command.target_ip,
                command.command_payload,
                max_duration=self._max_block_seconds,
            )
        except ValueError as error:
            return False, str(error)
        # Unblocking an owned action restores connectivity; do not prevent recovery
        # merely because an address was added to protection after the block.
        if command.action_type == PolicyActionType.UNBLOCK_IP_NFTABLES.value:
            if not command.command_payload.get("original_defense_action_id"):
                return False, "Unblock requires an original defense action ID"
            return True, None

        if command.action_type == PolicyActionType.CLEAR_OS_CACHE.value:
            return True, None

        if command.action_type == PolicyActionType.RESTART_SERVICE.value:
            service_name = (
                command.command_payload.get("service_name")
                or command.command_payload.get("target")
                or command.target_ip
            )
            if not service_name or not isinstance(service_name, str):
                return False, "Service name is required for RESTART_SERVICE"
            protected_services = {
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
            if service_name.lower().strip() in protected_services:
                return (
                    False,
                    f"Service '{service_name}' is a protected system service and "
                    "cannot be restarted",
                )
            return True, None
        # 1. Action type validation
        allowed_actions = {a.value for a in PolicyActionType}
        if command.action_type not in allowed_actions:
            return False, f"Action type '{command.action_type}' is not supported"

        if (
            command.action_type == PolicyActionType.UNBLOCK_IP_NFTABLES.value
            and not command.target_ip
        ):
            return False, "Target IP is required for UNBLOCK_IP_NFTABLES"

        # 2. Target IP validation (if command specifies a target IP)
        if command.target_ip:
            try:
                target_obj = ipaddress.ip_address(command.target_ip)
            except ValueError:
                return False, f"Invalid target IP address: {command.target_ip}"

            # Check loopback
            if (
                target_obj.is_loopback
                or target_obj.is_unspecified
                or target_obj.is_multicast
                or target_obj.is_link_local
            ):
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
                    try:
                        addresses = {
                            ipaddress.ip_address(str(info[4][0]).split("%")[0])
                            for info in socket.getaddrinfo(ctrl_host, None, type=socket.SOCK_STREAM)
                        }
                    except OSError:
                        return False, "Cannot resolve Controller addresses; blocking refused"
                    if target_obj in addresses:
                        return False, "Target matches a resolved Controller address"

            # Check local host interfaces (cannot block own node)
            try:
                local_ips = self._get_local_ips()
            except RuntimeError:
                return False, "Cannot inspect local interface protection; blocking refused"
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
