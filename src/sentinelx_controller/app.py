"""Create and setup FastAPI app for SentinelX Controller."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sentinelx_common.observability.logging import setup_logging
from sentinelx_controller.api.middleware.correlation import CorrelationIdMiddleware
from sentinelx_controller.api.v1.router import api_v1_router
from sentinelx_controller.config import ControllerSettings
from sentinelx_controller.infrastructure.database.session import (
    close_db_engine,
    get_session_factory,
    init_db_engine,
)
from sentinelx_controller.infrastructure.realtime import get_realtime_hub
from sentinelx_controller.maintenance import run_supervisor_tick

logger = logging.getLogger(__name__)


async def _supervisor_loop(
    settings: ControllerSettings,
    stop_event: asyncio.Event,
    interval_seconds: float = 15.0,
) -> None:
    """Periodically scan expired defense actions and transition silent nodes offline."""
    hub = get_realtime_hub()
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            break
        except TimeoutError:
            pass
        if stop_event.is_set():
            break
        try:
            summary = await run_supervisor_tick(
                settings=settings,
                session_factory=get_session_factory(),
                realtime_hub=hub,
            )
            if summary["reverted_actions"] or summary["offline_nodes"]:
                logger.info(
                    "Controller supervisor cycle completed",
                    extra=summary,
                )
        except asyncio.CancelledError:
            raise
        except Exception as err:
            logger.warning("Controller supervisor cycle skipped (%s): %s", type(err).__name__, err)


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
    init_db_engine(settings.database)
    stop_event = asyncio.Event()
    supervisor_task: asyncio.Task[None] | None = None
    if settings.environment != "testing":
        supervisor_task = asyncio.create_task(_supervisor_loop(settings, stop_event))
    try:
        yield
    finally:
        stop_event.set()
        if supervisor_task is not None:
            supervisor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await supervisor_task
        await close_db_engine()
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
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Add API routes
    app.include_router(api_v1_router)

    return app
