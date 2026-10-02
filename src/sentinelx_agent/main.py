"""Main entry point for SentinelX Agent daemon."""

import asyncio
import logging
import os
import signal
import sys

logging.basicConfig(
    level=os.getenv("SENTINELX_AGENT_LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("sentinelx_agent")


async def heartbeat_loop(controller_url: str, node_id: str, interval: int) -> None:
    """Send periodic mock heartbeat to the Controller."""
    logger.info(
        "Starting Agent heartbeat loop. Controller: %s, Node ID: %s",
        controller_url,
        node_id,
    )
    while True:
        logger.debug("Heartbeat ping -> %s for node %s", controller_url, node_id)
        await asyncio.sleep(interval)


async def main() -> None:
    """Run the Agent service."""
    controller_url = os.getenv("SENTINELX_CONTROLLER_URL", "http://controller:8000")
    node_id = os.getenv("SENTINELX_NODE_ID", os.getenv("HOSTNAME", "agent-unknown"))
    interval = int(os.getenv("SENTINELX_HEARTBEAT_INTERVAL", "5"))

    logger.info("Initializing SentinelX Agent [Node: %s]...", node_id)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _shutdown() -> None:
        logger.info("Received termination signal. Shutting down Agent...")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            # Signal handling on Windows event loop fallback
            pass

    task = asyncio.create_task(heartbeat_loop(controller_url, node_id, interval))

    await stop_event.wait()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("SentinelX Agent stopped cleanly.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
