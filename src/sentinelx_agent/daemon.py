"""Main daemon lifecycle orchestrator for SentinelX Agent."""

import asyncio
import logging
from datetime import UTC, datetime

import aiohttp

from sentinelx_agent.client import ControllerClient, ControllerClientError
from sentinelx_agent.config import AgentSettings
from sentinelx_agent.identity import AgentIdentity, AgentIdentityManager
from sentinelx_common.contracts.agents import AgentEnrollRequest, HeartbeatRequest

logger = logging.getLogger("sentinelx_agent.daemon")


class AgentDaemon:
    """Agent daemon controlling identity bootstrap and periodic heartbeat loop."""

    def __init__(
        self,
        settings: AgentSettings,
        client: ControllerClient | None = None,
    ) -> None:
        self.settings = settings
        self._client = client or ControllerClient(
            controller_url=settings.controller_url,
            timeout_seconds=settings.timeout_seconds,
        )
        self._owns_client = client is None
        self._identity: AgentIdentity | None = None
        self._stop_event = asyncio.Event()

    @property
    def identity(self) -> AgentIdentity | None:
        """Currently loaded or enrolled agent identity."""
        return self._identity

    async def bootstrap_identity(self) -> AgentIdentity:
        """Load existing identity from disk or perform enrollment handshake."""
        # 1. Attempt to load existing credentials
        existing = AgentIdentityManager.load(self.settings.identity_path)
        if existing is not None:
            self._identity = existing
            return existing

        # 2. Perform initial enrollment
        if not self.settings.node_id or not self.settings.enrollment_token:
            raise RuntimeError(
                "Cannot enroll Agent: node_id and enrollment_token must be configured "
                "when no identity file exists."
            )

        logger.info(
            "Performing initial Agent enrollment for node: %s",
            self.settings.node_id,
        )
        enroll_request = AgentEnrollRequest(
            node_id=self.settings.node_id,
            enrollment_token=self.settings.enrollment_token,
            agent_version=self.settings.agent_version,
            hostname=self.settings.hostname,
            os_info=self.settings.os_info,
        )

        resp = await self._client.enroll(enroll_request)
        identity = AgentIdentity(
            node_id=resp.node_id,
            agent_id=resp.agent_id,
            status=resp.status,
            enrolled_at=resp.enrolled_at,
        )

        AgentIdentityManager.save(self.settings.identity_path, identity)
        self._identity = identity
        logger.info("Agent enrolled successfully. Issued agent_id: %s", identity.agent_id)
        return identity

    async def run(self, stop_event: asyncio.Event | None = None) -> None:
        """Run daemon lifecycle: bootstrap identity then maintain heartbeat loop."""
        if stop_event is not None:
            self._stop_event = stop_event

        logger.info(
            "Starting SentinelX Agent daemon [Controller: %s, Hostname: %s]...",
            self.settings.controller_url,
            self.settings.hostname,
        )

        # Bootstrap identity with retry if controller is not yet ready
        retry_delay = self.settings.retry_initial_delay_seconds
        while not self._stop_event.is_set():
            try:
                await self.bootstrap_identity()
                break
            except (ControllerClientError, aiohttp.ClientError, OSError) as err:
                logger.warning(
                    "Identity bootstrap failed (%s). Retrying in %.1fs...",
                    err,
                    retry_delay,
                )
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=retry_delay)
                except TimeoutError:
                    pass
                retry_delay = min(
                    retry_delay * self.settings.retry_backoff_factor,
                    self.settings.retry_max_delay_seconds,
                )

        if self._stop_event.is_set() or self._identity is None:
            await self.shutdown()
            return

        # Start heartbeat loop
        await self._heartbeat_loop()

    async def _heartbeat_loop(self) -> None:
        """Periodic heartbeat loop with exponential backoff on failure."""
        assert self._identity is not None
        sequence = 1
        current_delay = self.settings.retry_initial_delay_seconds
        next_interval = float(self.settings.heartbeat_interval_seconds)

        logger.info("Agent heartbeat loop started (node_id=%s)", self._identity.node_id)

        while not self._stop_event.is_set():
            req = HeartbeatRequest(
                node_id=self._identity.node_id,
                agent_id=self._identity.agent_id,
                sequence=sequence,
                sent_at=datetime.now(UTC),
            )

            try:
                resp = await self._client.send_heartbeat(req)
                sequence += 1
                current_delay = self.settings.retry_initial_delay_seconds
                next_interval = float(resp.next_interval_seconds)
                logger.debug(
                    "Heartbeat acknowledged (seq=%d, next_interval=%.1fs)",
                    sequence - 1,
                    next_interval,
                )
                # Wait for next heartbeat interval or until stopped
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=next_interval)
                except TimeoutError:
                    pass

            except (ControllerClientError, aiohttp.ClientError, TimeoutError) as err:
                logger.warning(
                    "Heartbeat failed [seq=%d]: %s. Retrying in %.1fs...",
                    sequence,
                    err,
                    current_delay,
                )
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=current_delay)
                except TimeoutError:
                    pass
                current_delay = min(
                    current_delay * self.settings.retry_backoff_factor,
                    self.settings.retry_max_delay_seconds,
                )

        await self.shutdown()

    async def shutdown(self) -> None:
        """Cleanly stop daemon and release client resources."""
        self._stop_event.set()
        if self._owns_client:
            await self._client.close()
        logger.info("SentinelX Agent daemon shut down cleanly.")
