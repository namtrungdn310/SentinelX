"""Main daemon lifecycle orchestrator for SentinelX Agent."""

import asyncio
import logging
from datetime import UTC, datetime

import aiohttp

from sentinelx_agent.client import ControllerClient, ControllerClientError
from sentinelx_agent.collectors.base import MetricCollector
from sentinelx_agent.collectors.fake import FakeMetricGenerator
from sentinelx_agent.collectors.real import RealResourceCollector
from sentinelx_agent.config import AgentSettings
from sentinelx_agent.identity import AgentIdentity, AgentIdentityManager
from sentinelx_agent.telemetry import TelemetryBatcher
from sentinelx_common.contracts.agents import AgentEnrollRequest, HeartbeatRequest
from sentinelx_common.contracts.telemetry import MetricBatchRequest

logger = logging.getLogger("sentinelx_agent.daemon")


class AgentDaemon:
    """Agent daemon controlling identity bootstrap, heartbeat loop, and telemetry collection."""

    def __init__(
        self,
        settings: AgentSettings,
        client: ControllerClient | None = None,
        collector: MetricCollector | None = None,
        batcher: TelemetryBatcher | None = None,
    ) -> None:
        self.settings = settings
        self._client = client or ControllerClient(
            controller_url=settings.controller_url,
            timeout_seconds=settings.timeout_seconds,
        )
        self._owns_client = client is None

        # Khởi tạo Collector linh hoạt: ưu tiên injected collector -> sau đó kiểm tra config
        if collector is not None:
            self._collector: MetricCollector = collector
        elif settings.telemetry_collector_type.lower() == "fake":
            self._collector = FakeMetricGenerator()
        else:
            self._collector = RealResourceCollector(disk_path=settings.telemetry_disk_path)

        self._batcher = batcher or TelemetryBatcher()
        self._identity: AgentIdentity | None = None
        self._stop_event = asyncio.Event()
        self._telemetry_sequence: int = 1

    @property
    def identity(self) -> AgentIdentity | None:
        """Currently loaded or enrolled agent identity."""
        return self._identity

    @property
    def batcher(self) -> TelemetryBatcher:
        """Telemetry batcher buffer."""
        return self._batcher

    @property
    def collector(self) -> MetricCollector:
        """Metric collector."""
        return self._collector

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
        """Run daemon lifecycle: bootstrap identity then maintain heartbeat and telemetry loops."""
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

        # Concurrently run heartbeat loop and telemetry collection loop
        try:
            await asyncio.gather(
                self._heartbeat_loop(),
                self._telemetry_loop(),
            )
        finally:
            await self.shutdown()

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

    async def _telemetry_loop(self) -> None:
        """Periodic metric collection and batch dispatching loop."""
        assert self._identity is not None
        current_delay = self.settings.retry_initial_delay_seconds
        interval = float(self.settings.telemetry_interval_seconds)

        logger.info(
            "Agent telemetry loop started (interval=%.1fs, batch_size=%d, collector=%s)",
            interval,
            self.settings.telemetry_batch_size,
            type(self._collector).__name__,
        )

        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except TimeoutError:
                pass

            if self._stop_event.is_set():
                break

            # Thu thập metric trong worker thread - không bao giờ chặn asyncio event loop
            sample = await asyncio.to_thread(self._collector.collect)
            self._batcher.add(sample)

            if self._batcher.is_ready(self.settings.telemetry_batch_size):
                samples_to_send = self._batcher.drain(self.settings.telemetry_batch_size)
                batch_req = MetricBatchRequest(
                    node_id=self._identity.node_id,
                    agent_id=self._identity.agent_id,
                    sequence=self._telemetry_sequence,
                    sent_at=datetime.now(UTC),
                    samples=samples_to_send,
                )
                try:
                    resp = await self._client.send_metrics(batch_req)
                    self._telemetry_sequence += 1
                    current_delay = self.settings.retry_initial_delay_seconds
                    logger.debug(
                        "Telemetry batch acknowledged (seq=%d, processed=%d)",
                        self._telemetry_sequence - 1,
                        resp.processed_count,
                    )
                except (ControllerClientError, aiohttp.ClientError, TimeoutError) as err:
                    logger.warning(
                        "Telemetry batch dispatch failed [seq=%d]: %s. Re-buffering...",
                        self._telemetry_sequence,
                        err,
                    )
                    for s in reversed(samples_to_send):
                        self._batcher.add(s)
                    try:
                        await asyncio.wait_for(self._stop_event.wait(), timeout=current_delay)
                    except TimeoutError:
                        pass
                    current_delay = min(
                        current_delay * self.settings.retry_backoff_factor,
                        self.settings.retry_max_delay_seconds,
                    )

    async def shutdown(self) -> None:
        """Cleanly stop daemon and release client resources."""
        self._stop_event.set()
        if self._owns_client:
            await self._client.close()
        logger.info("SentinelX Agent daemon shut down cleanly.")
