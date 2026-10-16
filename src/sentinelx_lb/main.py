"""CLI entrypoint for SentinelX Load Balancer daemon."""

import logging
import sys

from aiohttp import web

from sentinelx_lb.config import LBSettings
from sentinelx_lb.server import create_app


def setup_logging(log_level: str) -> logging.Logger:
    """Configure structured console logging for the LB service."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    )
    return logging.getLogger("sentinelx_lb")


def main() -> None:
    """Load settings and start the aiohttp web server."""
    settings = LBSettings()
    logger = setup_logging(settings.log_level)

    logger.info("Starting SentinelX Load Balancer...")
    logger.info("Listening on: %s:%d", settings.host, settings.port)
    logger.info("Routing Algorithm: %s", settings.algorithm.value)
    logger.info("Configured Backends: %d targets", len(settings.backends))
    for idx, b in enumerate(settings.backends):
        logger.info("  [%d] %s (%s)", idx + 1, b.url, b.name or "unnamed")

    app = create_app(settings=settings)
    web.run_app(
        app,
        host=settings.host,
        port=settings.port,
        print=None,  # Avoid default aiohttp banner clashing with structured logging
    )


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
