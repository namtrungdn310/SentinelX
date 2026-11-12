"""Base defense executor contract for SentinelX Agent."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from sentinelx_common.contracts.defense import AgentCommandContract


class ExecutionResult(BaseModel):
    """Outcome of executing a defense command locally on the Agent host."""

    success: bool = Field(..., description="Whether the local command succeeded")
    error_message: str | None = Field(default=None, description="Error details if execution failed")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Execution details (output, duration, rule tags)",
    )


class BaseDefenseExecutor(ABC):
    """Abstract interface for local command executors."""

    @abstractmethod
    async def execute(self, command: AgentCommandContract) -> ExecutionResult:
        """Execute an authorized command and return execution outcome."""
