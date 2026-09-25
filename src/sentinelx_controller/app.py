"""Create and setup FastAPI app for SentinelX Controller."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from sentinelx_common.observability.logging import setup_logging
from sentinelx_controller.api.middleware.correlation import CorrelationIdMiddleware
from sentinelx_controller.api.v1.router import api_v1_router
from sentinelx_controller.config import ControllerSettings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle actions when the app starts and stops."""
    settings: ControllerSettings = app.state.settings
    logger.info(
        "Starting SentinelX Controller",
        extra={
            "environment": settings.environment,
            "version": settings.version,
            "host": settings.server.host,
            "port": settings.server.port,
        },
    )
    yield
    logger.info("Stopping SentinelX Controller")


def create_app(settings: ControllerSettings | None = None) -> FastAPI:
    """Create and setup the FastAPI app.

    Args:
        settings: Controller settings. If None, loads from file and environment.

    Returns:
        Ready-to-run FastAPI app.
    """
    if settings is None:
        settings = ControllerSettings.load()

    # Setup logging
    setup_logging(
        level=settings.logging.level,
        json_format=settings.logging.json_format,
        service_name=settings.service_name,
    )

    app = FastAPI(
        title="SentinelX Controller",
        description="Central Control Plane for SentinelX Infrastructure Management",
        version=settings.version,
        lifespan=lifespan,
    )

    # Save settings into app state
    app.state.settings = settings

    # Add middleware
    app.add_middleware(CorrelationIdMiddleware)

    # Add API routes
    app.include_router(api_v1_router)

    return app
