"""Aiohttp application factory and route registration for SentinelX Load Balancer."""

import logging

from aiohttp import ClientSession, web

from sentinelx_lb.balancer import LoadBalancer
from sentinelx_lb.config import LBSettings
from sentinelx_lb.pool import BackendPool
from sentinelx_lb.proxy import ReverseProxyHandler

logger = logging.getLogger("sentinelx_lb.server")


SETTINGS_KEY = web.AppKey("settings", LBSettings)
POOL_KEY = web.AppKey("pool", BackendPool)
BALANCER_KEY = web.AppKey("balancer", LoadBalancer)
CLIENT_SESSION_KEY = web.AppKey("client_session", ClientSession)
PROXY_HANDLER_KEY = web.AppKey("proxy_handler", ReverseProxyHandler)


async def health_check(_request: web.Request) -> web.Response:
    """Return health status of the Load Balancer daemon itself."""
    return web.json_response({
        "status": "healthy",
        "service": "sentinelx-lb",
        "version": "0.1.0",
    })


async def lb_status(request: web.Request) -> web.Response:
    """Return current operational state and pool telemetry."""
    balancer = request.app[BALANCER_KEY]
    pool = request.app[POOL_KEY]
    settings = request.app[SETTINGS_KEY]

    return web.json_response({
        "status": "active",
        "service": "sentinelx-lb",
        "algorithm": balancer.algorithm.value,
        "listen_host": settings.host,
        "listen_port": settings.port,
        "pool": pool.stats(),
    })


async def proxy_dispatcher(request: web.Request) -> web.StreamResponse:
    """Delegate incoming HTTP request to the ReverseProxyHandler."""
    handler = request.app[PROXY_HANDLER_KEY]
    return await handler.handle_proxy(request)


def create_app(settings: LBSettings | None = None) -> web.Application:
    """Build and configure the aiohttp Load Balancer web application."""
    if settings is None:
        settings = LBSettings()

    app = web.Application()

    pool = BackendPool.from_configs(settings.backends)
    balancer = LoadBalancer(pool=pool, algorithm=settings.algorithm)

    app[SETTINGS_KEY] = settings
    app[POOL_KEY] = pool
    app[BALANCER_KEY] = balancer

    async def on_startup(application: web.Application) -> None:
        session = ClientSession()
        handler = ReverseProxyHandler(
            balancer=balancer,
            session=session,
            client_timeout_seconds=settings.client_timeout_seconds,
        )
        application[CLIENT_SESSION_KEY] = session
        application[PROXY_HANDLER_KEY] = handler
        logger.info(
            "SentinelX LB initialized with %d backends (algorithm=%s)",
            len(settings.backends),
            balancer.algorithm.value,
        )

    async def on_cleanup(application: web.Application) -> None:
        session: ClientSession | None = application.get(CLIENT_SESSION_KEY)
        if session and not session.closed:
            await session.close()
            logger.info("Closed upstream ClientSession.")

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    # 1. Management and introspection endpoints
    app.router.add_get("/health", health_check)
    app.router.add_get("/lb/status", lb_status)

    # 2. Catch-all reverse proxy route (must be added last)
    app.router.add_route("*", "/{tail:.*}", proxy_dispatcher)

    return app
