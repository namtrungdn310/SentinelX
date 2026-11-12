"""nftables defense executor for SentinelX Agent."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
from collections.abc import Awaitable, Callable

from sentinelx_agent.defense.executors.base import BaseDefenseExecutor, ExecutionResult
from sentinelx_common.contracts.defense import AgentCommandContract
from sentinelx_common.contracts.policy import PolicyActionType

logger = logging.getLogger("sentinelx_agent.defense.executors.nftables")

# Type alias for async command runner: takes (cmd, stdin) -> (exit_code, stdout, stderr)
CommandRunner = Callable[[list[str], str | None], Awaitable[tuple[int, str, str]]]


async def _default_command_runner(
    cmd: list[str],
    stdin_text: str | None = None,
    timeout: float = 5.0,
) -> tuple[int, str, str]:
    """Execute a system command asynchronously without blocking the event loop."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE if stdin_text is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        input_bytes = stdin_text.encode("utf-8") if stdin_text is not None else None
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(input=input_bytes),
            timeout=timeout,
        )
        return (
            proc.returncode if proc.returncode is not None else -1,
            stdout_bytes.decode("utf-8", errors="replace"),
            stderr_bytes.decode("utf-8", errors="replace"),
        )
    except TimeoutError:
        try:
            proc.kill()
            await proc.wait()
        except (ProcessLookupError, OSError):
            pass
        return (-1, "", f"Command '{cmd[0]}' timed out after {timeout:.1f}s")
    except FileNotFoundError:
        return (-1, "", f"Binary '{cmd[0]}' not found on system PATH")
    except Exception as err:
        return (-1, "", f"Failed to execute command '{cmd[0]}': {err}")


class NftablesDefenseExecutor(BaseDefenseExecutor):
    """Executes network defense actions using the Linux kernel nftables packet filter."""

    def __init__(
        self,
        table_name: str = "sentinelx",
        nft_bin: str = "nft",
        command_runner: CommandRunner | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.table_name = table_name
        self.nft_bin = nft_bin
        self.timeout_seconds = timeout_seconds
        self._command_runner: CommandRunner = (
            command_runner
            if command_runner is not None
            else lambda cmd, stdin: _default_command_runner(
                cmd, stdin, timeout=self.timeout_seconds
            )
        )
        self._initialized = False
        self._init_lock = asyncio.Lock()

    def build_init_script(self) -> str:
        """Generate idempotent nftables script for SentinelX table, sets, and chains."""
        return (
            f"table inet {self.table_name} {{\n"
            f"    set blocked_v4 {{\n"
            f"        type ipv4_addr\n"
            f"        flags timeout\n"
            f"    }}\n"
            f"    set blocked_v6 {{\n"
            f"        type ipv6_addr\n"
            f"        flags timeout\n"
            f"    }}\n"
            f"    chain input {{\n"
            f"        type filter hook input priority -100; policy accept;\n"
            f"        ip saddr @blocked_v4 drop\n"
            f"        ip6 saddr @blocked_v6 drop\n"
            f"    }}\n"
            f"}}\n"
        )

    async def ensure_initialized(self) -> tuple[bool, str | None]:
        """Ensure the SentinelX nftables table, sets, and chain exist in the Linux kernel."""
        # Check if table already exists and contains required sets
        check_cmd = [self.nft_bin, "list", "table", "inet", self.table_name]
        code, stdout, _ = await self._command_runner(check_cmd, None)
        if code == 0 and "blocked_v4" in stdout and "blocked_v6" in stdout:
            return True, None

        # Apply schema configuration atomically via standard input
        init_script = self.build_init_script()
        apply_cmd = [self.nft_bin, "-f", "-"]
        code, _, stderr = await self._command_runner(apply_cmd, init_script)
        if code != 0:
            return False, f"nft -f - initialization failed (exit {code}): {stderr.strip()}"

        return True, None

    async def execute(self, command: AgentCommandContract) -> ExecutionResult:
        """Execute defense action on the local Linux host via nftables."""
        action_type = command.action_type
        if action_type not in (PolicyActionType.BLOCK_IP_NFTABLES.value, "UNBLOCK_IP_NFTABLES"):
            return ExecutionResult(
                success=False,
                error_message=f"Action '{action_type}' is not supported by NftablesDefenseExecutor",
            )

        if not command.target_ip:
            return ExecutionResult(
                success=False,
                error_message="Target IP is required for nftables defense action",
            )

        try:
            target_obj = ipaddress.ip_address(command.target_ip)
        except ValueError:
            return ExecutionResult(
                success=False,
                error_message=f"Invalid target IP address: {command.target_ip}",
            )

        set_name = "blocked_v4" if target_obj.version == 4 else "blocked_v6"

        # Lazy initialization
        async with self._init_lock:
            if not self._initialized:
                ok, err = await self.ensure_initialized()
                if not ok:
                    logger.error("Failed initializing nftables: %s", err)
                    return ExecutionResult(
                        success=False,
                        error_message=(
                            f"Failed to initialize nftables table '{self.table_name}': {err}"
                        ),
                    )
                self._initialized = True

        if action_type == PolicyActionType.BLOCK_IP_NFTABLES.value:
            return await self._execute_block_ip(command, target_obj, set_name)
        else:
            return await self._execute_unblock_ip(target_obj, set_name)

    async def _execute_block_ip(
        self,
        command: AgentCommandContract,
        target_obj: ipaddress.IPv4Address | ipaddress.IPv6Address,
        set_name: str,
    ) -> ExecutionResult:
        """Add IP to blocked set with timeout."""
        raw_duration = command.command_payload.get("duration_seconds")
        if raw_duration is None:
            raw_duration = command.command_payload.get("block_duration_seconds", 1800)

        try:
            duration_seconds = int(raw_duration) if raw_duration is not None else 1800
        except (ValueError, TypeError):
            duration_seconds = 1800

        if duration_seconds > 0:
            nft_cmd = [
                self.nft_bin,
                "add",
                "element",
                "inet",
                self.table_name,
                set_name,
                f"{{ {target_obj} timeout {duration_seconds}s }}",
            ]
        else:
            nft_cmd = [
                self.nft_bin,
                "add",
                "element",
                "inet",
                self.table_name,
                set_name,
                f"{{ {target_obj} }}",
            ]

        code, _, stderr = await self._command_runner(nft_cmd, None)
        if code != 0:
            logger.warning(
                "nftables add element failed: exit=%d, stderr=%s",
                code,
                stderr.strip(),
            )
            return ExecutionResult(
                success=False,
                error_message=f"nftables add element failed (exit {code}): {stderr.strip()}",
                metadata={"command": " ".join(nft_cmd), "exit_code": code},
            )

        logger.info(
            "Successfully blocked IP %s in nftables set %s (timeout: %ds)",
            target_obj,
            set_name,
            duration_seconds,
        )
        return ExecutionResult(
            success=True,
            metadata={
                "table": self.table_name,
                "set": set_name,
                "target_ip": str(target_obj),
                "duration_seconds": duration_seconds,
                "action": "BLOCK_IP_NFTABLES",
            },
        )

    async def _execute_unblock_ip(
        self,
        target_obj: ipaddress.IPv4Address | ipaddress.IPv6Address,
        set_name: str,
    ) -> ExecutionResult:
        """Remove IP from blocked set."""
        nft_cmd = [
            self.nft_bin,
            "delete",
            "element",
            "inet",
            self.table_name,
            set_name,
            f"{{ {target_obj} }}",
        ]

        code, _, stderr = await self._command_runner(nft_cmd, None)
        if code != 0:
            err_lower = stderr.lower()
            if "no such file or directory" in err_lower or "does not exist" in err_lower:
                logger.info(
                    "IP %s was not present in set %s (already expired or unblocked)",
                    target_obj,
                    set_name,
                )
                return ExecutionResult(
                    success=True,
                    metadata={
                        "table": self.table_name,
                        "set": set_name,
                        "target_ip": str(target_obj),
                        "status": "already_removed",
                    },
                )

            logger.warning(
                "nftables delete element failed: exit=%d, stderr=%s",
                code,
                stderr.strip(),
            )
            return ExecutionResult(
                success=False,
                error_message=f"nftables delete element failed (exit {code}): {stderr.strip()}",
                metadata={"command": " ".join(nft_cmd), "exit_code": code},
            )

        logger.info("Successfully unblocked IP %s from nftables set %s", target_obj, set_name)
        return ExecutionResult(
            success=True,
            metadata={
                "table": self.table_name,
                "set": set_name,
                "target_ip": str(target_obj),
                "action": "UNBLOCK_IP_NFTABLES",
            },
        )
