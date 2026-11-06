"""Isolated capture supervisor and bounded delivery; resource monitoring stays alive."""

import asyncio
import logging
import time
from collections import deque
from datetime import UTC, datetime
from uuid import UUID

from sentinelx_agent.client import ControllerClient
from sentinelx_agent.config import AgentSettings
from sentinelx_agent.identity import AgentIdentity
from sentinelx_agent.network.aggregation import SlidingWindowAggregator
from sentinelx_agent.network.capture import PacketCapture
from sentinelx_common.contracts.network import NetworkBatchRequest, NetworkWindow

logger = logging.getLogger("sentinelx_agent.network")


async def wait_stop(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except TimeoutError:
        pass


async def run_network(
    settings: AgentSettings, identity: AgentIdentity, client: ControllerClient, stop: asyncio.Event
) -> None:
    pending: deque[NetworkWindow] = deque(maxlen=16)
    sequence = 1
    retry = settings.retry_initial_delay_seconds
    while not stop.is_set():
        aggregator = SlidingWindowAggregator(
            settings.network_interface,
            window_seconds=settings.network_window_seconds,
            step_seconds=settings.network_step_seconds,
            max_groups=settings.network_max_groups,
            start_monotonic=time.monotonic(),
            start_utc=datetime.now(UTC),
        )
        capture = PacketCapture(settings.network_interface, settings.network_bpf_filter, aggregator)
        start = asyncio.create_task(asyncio.to_thread(capture.start))
        try:
            try:
                await asyncio.shield(start)
            except asyncio.CancelledError:
                await start
                raise
            logger.info("Network capture active on interface=%s", settings.network_interface)
            retry = settings.retry_initial_delay_seconds
            while not stop.is_set():
                await wait_stop(stop, settings.network_step_seconds)
                if stop.is_set():
                    break
                if not capture.running:
                    raise RuntimeError("Capture thread stopped; no zero-traffic windows fabricated")
                for window in aggregator.drain(time.monotonic()):
                    if len(pending) == pending.maxlen:
                        logger.warning("Network delivery buffer full; dropping oldest window")
                    pending.append(window)
                if pending:
                    batch = list(pending)[:4]
                    request = NetworkBatchRequest(
                        node_id=UUID(identity.node_id),
                        agent_id=UUID(identity.agent_id),
                        sequence=sequence,
                        sent_at=datetime.now(UTC),
                        windows=batch,
                    )
                    try:
                        await client.send_network(request)
                    except Exception as error:
                        logger.warning(
                            "Network delivery failed (%s); windows retained", type(error).__name__
                        )
                    else:
                        for _ in batch:
                            pending.popleft()
                        sequence += 1
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.warning(
                "Network capture unavailable (%s); resource monitoring continues",
                type(error).__name__,
            )
        finally:
            try:
                await asyncio.to_thread(capture.stop)
            except Exception as error:
                logger.warning("Capture cleanup failed (%s)", type(error).__name__)
        if not stop.is_set():
            await wait_stop(stop, retry)
            retry = min(retry * settings.retry_backoff_factor, settings.retry_max_delay_seconds)
