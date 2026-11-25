"""Service recovery and host resource mitigation executor for SentinelX Agent."""

from __future__ import annotations

import asyncio
import logging
import platform
import re
from collections.abc import Awaitable, Callable
from typing import Any

import psutil

from sentinelx_agent.collectors.real import RealResourceCollector
from sentinelx_agent.defense.executors.base import BaseDefenseExecutor, ExecutionResult
from sentinelx_common.contracts.command_parameters import is_protected_system_service
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
        if command.action_type == PolicyActionType.ADAPTIVE.value:
            return await self._execute_adaptive(command)

        return ExecutionResult(
            success=False,
            error_message=(
                f"Action '{command.action_type}' is not supported by ServiceRecoveryExecutor"
            ),
        )

    async def _execute_adaptive(self, command: AgentCommandContract) -> ExecutionResult:
        """Resolve ADAPTIVE locally: restart dominant >=40% app service, else clear OS cache."""
        payload = command.command_payload
        explicit_svc = payload.get("service_name") or payload.get("target")
        if (
            isinstance(explicit_svc, str)
            and explicit_svc.strip()
            and explicit_svc.strip().lower() not in {"adaptive", "os-cache"}
            and not is_protected_system_service(explicit_svc)
        ):
            return await self._restart_service(command)

        top_name, _, _, top_mem, _, top_cgroup = await asyncio.to_thread(
            RealResourceCollector._find_top_process,
            "memory",
            normalize_cpu=False,
        )
        host_mem = float(psutil.virtual_memory().percent or 0.0)
        if (
            top_name
            and top_mem is not None
            and host_mem > 0
            and (float(top_mem) / host_mem) >= 0.40
            and not is_protected_system_service(top_name)
        ):
            target_svc = top_cgroup or top_name
            resolved_cmd = command.model_copy(
                update={
                    "action_type": PolicyActionType.RESTART_SERVICE.value,
                    "command_payload": {**payload, "service_name": target_svc},
                }
            )
            result = await self._restart_service(resolved_cmd)
            result.metadata["adaptive_decision"] = "restart_service"
            return result

        result = await self._clear_os_cache(command)
        result.metadata["adaptive_decision"] = "clear_os_cache"
        return result

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
            detail = stderr.strip() or f"exit code {code}"
            return ExecutionResult(
                success=False,
                error_message=f"Failed to restart service {service_name}: {detail}",
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

        code, _stdout, stderr = await self._command_runner(
            ["sh", "-c", "sync && printf '3\\n' > /proc/sys/vm/drop_caches"],
            None,
        )
        if code != 0:
            detail = stderr.strip() or f"exit code {code}"
            logger.warning("OS cache clearing failed: %s", detail)
            metadata["drop_caches_applied"] = False
            return ExecutionResult(
                success=False,
                error_message=f"Failed to clear OS cache: {detail}",
                metadata=metadata,
            )

        metadata["drop_caches_applied"] = True
        return ExecutionResult(success=True, metadata=metadata)
