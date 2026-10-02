"""Main entry point for SentinelX Load Balancer."""

import logging
import os
import sys

from aiohttp import web

logging.basicConfig(
    level=os.getenv("SENTINELX_LB_LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("sentinelx_lb")


async def health_check(_request: web.Request) -> web.Response:
    """Return health status of the Load Balancer."""
    return web.json_response({
        "status": "healthy",
        "service": "sentinelx-lb",
        "version": "0.1.0",
    })


async def handle_proxy(request: web.Request) -> web.Response:
    """Fallback handler / proxy placeholder for Lab testing."""
    return web.json_response({
        "message": "SentinelX Load Balancer active",
        "path": request.path,
        "method": request.method,
    })


def create_app() -> web.Application:
    """Create and configure the aiohttp web application."""
    app = web.Application()
    app.router.add_get("/health", health_check)
    app.router.add_route("*", "/{tail:.*}", handle_proxy)
    return app


def main() -> None:
    """Run the Load Balancer HTTP server."""
    host = os.getenv("SENTINELX_LB_HOST", "0.0.0.0")
    port = int(os.getenv("SENTINELX_LB_PORT", "8080"))

    logger.info("Starting SentinelX Load Balancer on %s:%d...", host, port)
    app = create_app()
    web.run_app(app, host=host, port=port)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
