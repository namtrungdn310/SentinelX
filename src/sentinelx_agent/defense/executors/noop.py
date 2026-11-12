"""No-op defense executor."""

from sentinelx_agent.defense.executors.base import BaseDefenseExecutor, ExecutionResult
from sentinelx_common.contracts.defense import AgentCommandContract


class NoopDefenseExecutor(BaseDefenseExecutor):
    """No-op executor that safely ignores commands."""

    async def execute(self, command: AgentCommandContract) -> ExecutionResult:
        return ExecutionResult(
            success=True,
            metadata={"noop": True},
        )
