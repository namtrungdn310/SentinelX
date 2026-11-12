"""Command processor coordinating validation, execution, and acknowledgment on the Agent."""

import logging

from sentinelx_agent.client import ControllerClient, ControllerClientError
from sentinelx_agent.config import AgentSettings
from sentinelx_agent.defense.executors.base import BaseDefenseExecutor
from sentinelx_agent.defense.executors.nftables import NftablesDefenseExecutor
from sentinelx_agent.defense.executors.noop import NoopDefenseExecutor
from sentinelx_agent.defense.executors.simulated import SimulatedDefenseExecutor
from sentinelx_agent.defense.validator import LocalSafetyValidator
from sentinelx_common.contracts.defense import (
    AgentCommandContract,
    CommandAckRequest,
    CommandAckResponse,
    DefenseActionStatus,
)

logger = logging.getLogger("sentinelx_agent.defense.processor")


class CommandProcessor:
    """Coordinates receiving commands, local safety checks, execution, and sending ACK."""

    def __init__(
        self,
        settings: AgentSettings,
        executor: BaseDefenseExecutor | None = None,
        validator: LocalSafetyValidator | None = None,
    ) -> None:
        self.settings = settings
        self.validator = validator or LocalSafetyValidator()
        if executor is not None:
            self.executor = executor
        elif getattr(settings, "defense_executor_type", "simulated") == "noop":
            self.executor = NoopDefenseExecutor()
        elif getattr(settings, "defense_executor_type", "simulated") == "nftables":
            self.executor = NftablesDefenseExecutor(
                table_name=getattr(settings, "nftables_table_name", "sentinelx")
            )
        else:
            self.executor = SimulatedDefenseExecutor()

    async def process_command(
        self,
        command: AgentCommandContract,
        client: ControllerClient,
    ) -> CommandAckResponse | None:
        """Validate command locally, execute it, and submit ACK to Controller."""
        logger.info(
            "Processing defense command: id=%s action=%s target=%s",
            command.id,
            command.action_type,
            command.target_ip,
        )

        # 1. Local Safety Validation
        is_valid, rejection_reason = self.validator.validate(
            command=command,
            controller_url=self.settings.controller_url,
        )
        if not is_valid:
            logger.warning(
                "REJECTING command %s: local safety check failed: %s",
                command.id,
                rejection_reason,
            )
            ack_req = CommandAckRequest(
                action_id=command.id,
                status=DefenseActionStatus.FAILED,
                error_message=f"Local safety guardrail rejected: {rejection_reason}",
            )
            try:
                return await client.ack_defense_action(command.id, ack_req)
            except ControllerClientError as err:
                logger.error("Failed sending rejection ACK for %s: %s", command.id, err)
                return None

        # 2. Execution via configured executor
        try:
            result = await self.executor.execute(command)
        except Exception as err:
            logger.exception("Unexpected error executing command %s: %s", command.id, err)
            ack_req = CommandAckRequest(
                action_id=command.id,
                status=DefenseActionStatus.FAILED,
                error_message=f"Execution error: {err}",
            )
            try:
                return await client.ack_defense_action(command.id, ack_req)
            except ControllerClientError as ack_err:
                logger.error("Failed sending error ACK for %s: %s", command.id, ack_err)
                return None

        # 3. Report execution outcome
        status = DefenseActionStatus.APPLIED if result.success else DefenseActionStatus.FAILED
        ack_req = CommandAckRequest(
            action_id=command.id,
            status=status,
            error_message=result.error_message,
            execution_metadata=result.metadata,
        )
        try:
            resp = await client.ack_defense_action(command.id, ack_req)
            logger.info(
                "Command %s acknowledged successfully (status=%s)",
                command.id,
                status.value,
            )
            return resp
        except ControllerClientError as err:
            logger.error("Failed sending ACK for command %s: %s", command.id, err)
            return None
