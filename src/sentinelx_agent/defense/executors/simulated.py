"""Simulated defense executor for testing and Safe Mode."""

import logging
from datetime import UTC, datetime

from sentinelx_agent.defense.executors.base import BaseDefenseExecutor, ExecutionResult
from sentinelx_common.contracts.defense import AgentCommandContract

logger = logging.getLogger("sentinelx_agent.defense.executors.simulated")


class SimulatedDefenseExecutor(BaseDefenseExecutor):
    """Simulates execution of commands without modifying system firewall or processes."""

    async def execute(self, command: AgentCommandContract) -> ExecutionResult:
        logger.info(
            "[SIMULATED DEFENSE] Executing action=%s target_ip=%s payload=%s",
            command.action_type,
            command.target_ip,
            command.command_payload,
        )
        return ExecutionResult(
            success=True,
            metadata={
                "simulated": True,
                "executed_at": datetime.now(UTC).isoformat(),
                "action_type": command.action_type,
                "target_ip": command.target_ip,
            },
        )
