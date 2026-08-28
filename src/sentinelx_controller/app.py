"""FastAPI Application Factory for SentinelX Controller."""

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
    """Lifespan context manager managing startup and shutdown lifecycles."""
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
    """Create and configure a new FastAPI application instance.

    Args:
        settings: Optional ControllerSettings instance. If None, loads defaults/YAML/env.

    Returns:
        Configured FastAPI application.
    """
    if settings is None:
        settings = ControllerSettings.load()

    # Configure structured logging
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

    # Store settings in application state
    app.state.settings = settings

    # Add middlewares
    app.add_middleware(CorrelationIdMiddleware)

    # Mount API routers
    app.include_router(api_v1_router)

    return app
