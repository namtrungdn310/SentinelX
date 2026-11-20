"""Independent command worker with durable execution receipts and ACK retries."""

import asyncio
import logging
import sqlite3
from datetime import UTC, datetime, timedelta

import aiohttp

from sentinelx_agent.client import ControllerClient, ControllerClientError
from sentinelx_agent.config import AgentSettings
from sentinelx_agent.defense.executors.base import BaseDefenseExecutor
from sentinelx_agent.defense.executors.nftables import NftablesDefenseExecutor
from sentinelx_agent.defense.executors.noop import NoopDefenseExecutor
from sentinelx_agent.defense.executors.recovery import ServiceRecoveryExecutor
from sentinelx_agent.defense.executors.simulated import SimulatedDefenseExecutor
from sentinelx_agent.defense.journal import CommandJournal
from sentinelx_agent.defense.validator import LocalSafetyValidator
from sentinelx_agent.identity import AgentIdentity
from sentinelx_common.contracts.command_parameters import SUPPORTED_ACTIONS
from sentinelx_common.contracts.defense import (
    AgentCommandContract,
    CommandAckRequest,
    CommandAckResponse,
    DefenseActionStatus,
)

logger = logging.getLogger("sentinelx_agent.defense.processor")


class CommandProcessor:
    def __init__(
        self,
        settings: AgentSettings,
        executor: BaseDefenseExecutor | None = None,
        validator: LocalSafetyValidator | None = None,
    ) -> None:
        self.settings = settings
        self.validator = validator or LocalSafetyValidator(
            settings.protected_cidrs,
            settings.max_block_seconds,
        )
        if executor is not None:
            self.executor = executor
        elif settings.defense_executor_type == "nftables":
            self.executor = NftablesDefenseExecutor(
                table_name=settings.nftables_table_name,
                hook=settings.nftables_hook,
            )
        elif settings.defense_executor_type == "noop":
            self.executor = NoopDefenseExecutor()
        else:
            self.executor = SimulatedDefenseExecutor()
        self.recovery_executor = ServiceRecoveryExecutor()
        self.journal = CommandJournal(
            settings.command_journal_path or settings.identity_path.with_name("commands.sqlite3"),
        )
        self._identity: AgentIdentity | None = None
        self._queue: asyncio.Queue[AgentCommandContract] = asyncio.Queue(
            settings.command_queue_size
        )
        self._queued_ids: set[str] = set()
        self._lock = asyncio.Lock()

    @property
    def supported_actions(self) -> list[str]:
        return sorted(SUPPORTED_ACTIONS)

    def set_identity(self, identity: AgentIdentity) -> None:
        self._identity = identity

    def enqueue(self, command: AgentCommandContract) -> None:
        if command.id in self._queued_ids:
            return
        try:
            self._queue.put_nowait(command)
            self._queued_ids.add(command.id)
        except asyncio.QueueFull:
            logger.warning("Command queue full; Controller lease will make command eligible again")

    async def _send_ack(
        self,
        request: CommandAckRequest,
        client: ControllerClient,
    ) -> CommandAckResponse | None:
        try:
            response = await client.ack_defense_action(request.action_id, request)
        except (ControllerClientError, aiohttp.ClientError, TimeoutError, OSError) as error:
            logger.warning(
                "ACK pending for command %s (%s)", request.action_id, type(error).__name__
            )
            await asyncio.to_thread(self.journal.defer_ack, request.action_id)
            return None
        await asyncio.to_thread(self.journal.acknowledge, request.action_id)
        return response

    async def process_command(
        self,
        command: AgentCommandContract,
        client: ControllerClient,
    ) -> CommandAckResponse | None:
        async with self._lock:
            if self._identity and command.node_id != self._identity.node_id:
                logger.error("Rejected command addressed to a different node")
                return None
            try:
                reservation = await asyncio.to_thread(self.journal.reserve, command)
            except (ValueError, RuntimeError, OSError, sqlite3.Error) as error:
                logger.error("Command journal refused execution: %s", error)
                return None
            if reservation is None:
                return None
            stored, receipt = reservation
            if receipt is not None:
                return await self._send_ack(receipt, client)
            now = datetime.now(UTC)
            valid, reason = await asyncio.to_thread(
                self.validator.validate,
                stored,
                self.settings.controller_url,
            )
            state = DefenseActionStatus.FAILED
            metadata: dict[str, object] = {"executor": self.settings.defense_executor_type}
            if valid:
                try:
                    if stored.action_type == "ALERT_ONLY":
                        state = DefenseActionStatus.SKIPPED
                        metadata["alert_only"] = True
                    else:
                        active_executor: BaseDefenseExecutor
                        if stored.action_type in ("RESTART_SERVICE", "CLEAR_OS_CACHE"):
                            active_executor = (
                                self.executor
                                if isinstance(
                                    self.executor, (SimulatedDefenseExecutor, NoopDefenseExecutor)
                                )
                                else self.recovery_executor
                            )
                        else:
                            active_executor = self.executor
                        outcome = await active_executor.execute(stored)
                        metadata.update(outcome.metadata)
                        reason = outcome.error_message
                        if outcome.success:
                            if outcome.metadata.get("simulated"):
                                state = DefenseActionStatus.SIMULATED
                            elif outcome.metadata.get("noop"):
                                state = DefenseActionStatus.SKIPPED
                            elif outcome.metadata.get("executor") in (
                                "nftables",
                                "service_recovery",
                            ):
                                state = DefenseActionStatus.APPLIED
                            else:
                                reason = "Executor did not identify a verified real outcome"
                except Exception as error:
                    logger.exception("Executor failed for command %s", stored.id)
                    reason = f"Executor error: {type(error).__name__}"
            executed = now
            if (
                stored.action_type == "BLOCK_IP_NFTABLES"
                and "effective_until" in stored.command_payload
            ):
                executed = datetime.fromisoformat(
                    stored.command_payload["effective_until"]
                ) - timedelta(
                    seconds=stored.command_payload.get(
                        "duration_seconds",
                        stored.command_payload.get("block_duration_seconds", 1800),
                    ),
                )
            result = CommandAckRequest(
                action_id=stored.id,
                status=state,
                node_id=self._identity.node_id if self._identity else self.settings.node_id,
                agent_id=self._identity.agent_id if self._identity else None,
                delivery_token=command.delivery_token,
                executed_at=executed,
                error_message=reason,
                execution_metadata=metadata,
            )
            await asyncio.to_thread(self.journal.complete, stored.id, result)
            return await self._send_ack(result, client)

    async def run(self, client: ControllerClient, stop: asyncio.Event) -> None:
        await self.reconcile_kernel()
        while not stop.is_set():
            try:
                for receipt in await asyncio.to_thread(self.journal.pending):
                    if stop.is_set():
                        return
                    await self._send_ack(receipt, client)
            except (OSError, ValueError, RuntimeError, sqlite3.Error):
                logger.exception("Command journal unavailable; execution remains fail-closed")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=5)
                except TimeoutError:
                    pass
                continue
            try:
                command = await asyncio.wait_for(self._queue.get(), timeout=1)
            except TimeoutError:
                continue
            try:
                await self.process_command(command, client)
            except (OSError, ValueError, RuntimeError, sqlite3.Error):
                # A damaged/unwritable journal is visible and never causes unjournaled execution.
                logger.exception("Command worker failed; execution remains fail-closed")
            finally:
                self._queued_ids.discard(command.id)
                self._queue.task_done()

    async def reconcile_kernel(self) -> None:
        """Restore only our unexpired real blocks after restart, without extending TTL."""
        if not isinstance(self.executor, NftablesDefenseExecutor):
            return
        try:
            commands = await asyncio.to_thread(self.journal.active_blocks)
            for command in commands:
                if self._identity is None or command.node_id != self._identity.node_id:
                    continue
                now = datetime.now(UTC)
                # Revalidate address protection now; original delivery expiry is not a new lease.
                validation = command.model_copy(
                    update={"created_at": now, "expires_at": now + timedelta(seconds=30)}
                )
                valid, reason = await asyncio.to_thread(
                    self.validator.validate, validation, self.settings.controller_url
                )
                if not valid:
                    logger.error("Kernel reconciliation refused for %s: %s", command.id, reason)
                    continue
                outcome = await self.executor.execute(command)
                if not outcome.success:
                    logger.error(
                        "Kernel reconciliation required for %s: %s",
                        command.id,
                        outcome.error_message,
                    )
        except (OSError, ValueError, RuntimeError, sqlite3.Error):
            logger.exception("Cannot reconcile kernel state; operator intervention required")
