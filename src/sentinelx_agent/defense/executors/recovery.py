"""Service recovery and host resource mitigation executor for SentinelX Agent."""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import re
from collections.abc import Awaitable, Callable
from typing import Any

from sentinelx_agent.defense.executors.base import BaseDefenseExecutor, ExecutionResult
from sentinelx_common.contracts.defense import AgentCommandContract
from sentinelx_common.contracts.policy import PolicyActionType

logger = logging.getLogger("sentinelx_agent.defense.executors.recovery")

CommandRunner = Callable[[list[str], str | None], Awaitable[tuple[int, str, str]]]


async def _default_command_runner(
    cmd: list[str],
    stdin_text: str | None = None,
    timeout: float = 10.0,
) -> tuple[int, str, str]:
    proc: asyncio.subprocess.Process | None = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE if stdin_text is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(stdin_text.encode() if stdin_text is not None else None),
            timeout,
        )
        return (
            proc.returncode or 0,
            stdout.decode(errors="replace"),
            stderr.decode(errors="replace"),
        )
    except (TimeoutError, asyncio.CancelledError) as error:
        if proc is not None:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
        if isinstance(error, asyncio.CancelledError):
            raise
        return -1, "", f"Command timed out after {timeout}s"
    except OSError as error:
        return -1, "", f"Cannot execute {cmd[0]}: {type(error).__name__}"


class ServiceRecoveryExecutor(BaseDefenseExecutor):
    """Executes service restarts (systemd/docker) and host OS cache clearing."""

    def __init__(
        self,
        command_runner: CommandRunner | None = None,
        managed_services: list[str] | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._command_runner = command_runner or _default_command_runner
        self._managed_services = set(managed_services) if managed_services else set()
        self._timeout_seconds = timeout_seconds

    async def execute(self, command: AgentCommandContract) -> ExecutionResult:
        if command.action_type == PolicyActionType.RESTART_SERVICE.value:
            return await self._restart_service(command)
        if command.action_type == PolicyActionType.CLEAR_OS_CACHE.value:
            return await self._clear_os_cache(command)

        return ExecutionResult(
            success=False,
            error_message=(
                f"Action '{command.action_type}' is not supported by ServiceRecoveryExecutor"
            ),
        )

    async def _restart_service(self, command: AgentCommandContract) -> ExecutionResult:
        payload = command.command_payload
        raw_service = payload.get("service_name") or payload.get("target") or command.target_ip
        if not raw_service or not isinstance(raw_service, str):
            return ExecutionResult(
                success=False,
                error_message="Service name is required for RESTART_SERVICE",
            )

        service_name = raw_service.strip()
        if not re.fullmatch(r"[a-zA-Z0-9_\-\.]{1,64}", service_name):
            return ExecutionResult(
                success=False,
                error_message=f"Invalid service identifier: {service_name}",
            )

        # In Linux production, execute systemctl restart
        is_linux = platform.system() == "Linux"
        metadata: dict[str, Any] = {
            "executor": "service_recovery",
            "action": "restart_service",
            "service_name": service_name,
        }

        if not is_linux:
            logger.info("Non-Linux host; simulated service restart for: %s", service_name)
            metadata["simulated_platform"] = platform.system()
            return ExecutionResult(success=True, metadata=metadata)

        # Execute systemctl restart
        cmd = ["systemctl", "restart", service_name]
        code, stdout, stderr = await self._command_runner(cmd, None)
        if code != 0:
            logger.warning("systemctl restart %s failed: %s", service_name, stderr)
            # If systemd is not present (e.g. lightweight docker container), fallback gracefully
            if "Cannot execute" in stderr or "not found" in stderr.lower():
                metadata["fallback_reason"] = stderr.strip()
                return ExecutionResult(success=True, metadata=metadata)
            return ExecutionResult(
                success=False,
                error_message=f"Failed to restart service {service_name}: {stderr.strip()}",
                metadata=metadata,
            )

        metadata["stdout"] = stdout.strip()
        return ExecutionResult(success=True, metadata=metadata)

    async def _clear_os_cache(self, command: AgentCommandContract) -> ExecutionResult:
        metadata: dict[str, Any] = {
            "executor": "service_recovery",
            "action": "clear_os_cache",
        }

        is_linux = platform.system() == "Linux"
        if not is_linux:
            logger.info("Non-Linux host; simulated OS cache clearing")
            metadata["simulated_platform"] = platform.system()
            return ExecutionResult(success=True, metadata=metadata)

        # Call sync
        await self._command_runner(["sync"], None)

        # Drop pagecache, dentries, and inodes via /proc/sys/vm/drop_caches if writable
        try:
            drop_path = "/proc/sys/vm/drop_caches"
            if os.path.exists(drop_path) and os.access(drop_path, os.W_OK):
                with open(drop_path, "w", encoding="utf-8") as f:
                    f.write("3\n")
                metadata["drop_caches_applied"] = True
            else:
                metadata["drop_caches_applied"] = False
                metadata["note"] = "Insufficient privileges or /proc/sys/vm/drop_caches unwriteable"
        except Exception as err:
            logger.warning("Could not write to drop_caches: %s", err)
            metadata["drop_caches_error"] = str(err)

        return ExecutionResult(success=True, metadata=metadata)
