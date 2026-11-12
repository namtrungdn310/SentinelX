"""Simulated defense executor for testing and Safe Mode."""

import logging
from datetime import UTC, datetime

from sentinelx_agent.defense.executors.base import BaseDefenseExecutor, ExecutionResult
from sentinelx_common.contracts.defense import AgentCommandContract
from sentinelx_common.contracts.policy import PolicyActionType

logger = logging.getLogger("sentinelx_agent.defense.executors.simulated")


class SimulatedDefenseExecutor(BaseDefenseExecutor):
    """Simulates execution of commands without modifying system firewall or processes."""

    def __init__(self) -> None:
        self.blocked_ips: set[str] = set()

    async def execute(self, command: AgentCommandContract) -> ExecutionResult:
        logger.info(
            "[SIMULATED DEFENSE] Executing action=%s target_ip=%s payload=%s",
            command.action_type,
            command.target_ip,
            command.command_payload,
        )

        if command.action_type == PolicyActionType.BLOCK_IP_NFTABLES.value and command.target_ip:
            self.blocked_ips.add(command.target_ip)
        elif (
            command.action_type == PolicyActionType.UNBLOCK_IP_NFTABLES.value
            and command.target_ip
        ):
            self.blocked_ips.discard(command.target_ip)

        return ExecutionResult(
            success=True,
            metadata={
                "simulated": True,
                "executed_at": datetime.now(UTC).isoformat(),
                "action_type": command.action_type,
                "target_ip": command.target_ip,
                "currently_blocked_count": len(self.blocked_ips),
            },
        )
