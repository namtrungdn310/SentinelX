"""Main entry point for SentinelX Agent daemon."""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

from sentinelx_agent.config import AgentSettings
from sentinelx_agent.daemon import AgentDaemon

logging.basicConfig(
    level=os.getenv("SENTINELX_AGENT_LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("sentinelx_agent")


async def main() -> None:
    """Run the SentinelX Agent service."""
    config_file = os.getenv("SENTINELX_AGENT_CONFIG")
    config_path = Path(config_file) if config_file else None
    settings = AgentSettings.load(config_path)

    daemon = AgentDaemon(settings=settings)
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _shutdown() -> None:
        logger.info("Received termination signal. Shutting down Agent...")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            # Signal handling fallback on Windows event loop
            pass

    await daemon.run(stop_event=stop_event)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
