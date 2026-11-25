"""Aiohttp application factory and route registration for SentinelX Load Balancer."""

import logging
import secrets
from typing import Any

from aiohttp import ClientSession, DummyCookieJar, web
from pydantic import ValidationError

from sentinelx_lb.balancer import LoadBalancer
from sentinelx_lb.config import BackendConfig, HealthCheckConfig, LBAlgorithm, LBSettings
from sentinelx_lb.health import ActiveHealthChecker
from sentinelx_lb.pool import BackendPool
from sentinelx_lb.proxy import ReverseProxyHandler

logger = logging.getLogger("sentinelx_lb.server")


SETTINGS_KEY = web.AppKey("settings", LBSettings)
POOL_KEY = web.AppKey("pool", BackendPool)
BALANCER_KEY = web.AppKey("balancer", LoadBalancer)
CLIENT_SESSION_KEY = web.AppKey("client_session", ClientSession)
PROXY_HANDLER_KEY = web.AppKey("proxy_handler", ReverseProxyHandler)
HEALTH_CHECKER_KEY = web.AppKey("health_checker", ActiveHealthChecker)


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
        "health_check": {
            "enabled": settings.health_check.enabled,
            "path": settings.health_check.path,
            "interval_seconds": settings.health_check.interval_seconds,
            "failure_threshold": settings.health_check.failure_threshold,
            "success_threshold": settings.health_check.success_threshold,
        },
        "pool": pool.stats(),
    })


async def proxy_dispatcher(request: web.Request) -> web.StreamResponse:
    """Delegate incoming HTTP request to the ReverseProxyHandler."""
    handler = request.app[PROXY_HANDLER_KEY]
    return await handler.handle_proxy(request)


def _authorize_admin(request: web.Request) -> web.Response | None:
    """Enforce SENTINELX_LB_ADMIN_TOKEN if configured on the LB daemon."""
    expected = request.app[SETTINGS_KEY].admin_token
    if not expected:
        return None
    auth_header = request.headers.get("Authorization", "")
    token = ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    elif "X-SentinelX-LB-Token" in request.headers:
        token = request.headers["X-SentinelX-LB-Token"].strip()
    if not token or not secrets.compare_digest(token, expected):
        return web.json_response({"error": "Unauthorized LB admin request"}, status=401)
    return None


async def update_lb_config(request: web.Request) -> web.Response:
    """Hot-update routing algorithm, backend pool, and health check settings."""
    denied = _authorize_admin(request)
    if denied is not None:
        return denied

    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    settings = request.app[SETTINGS_KEY]
    balancer = request.app[BALANCER_KEY]
    pool = request.app[POOL_KEY]
    health_checker = request.app[HEALTH_CHECKER_KEY]

    if "algorithm" in payload and payload["algorithm"] is not None:
        try:
            algo = LBAlgorithm(str(payload["algorithm"]))
        except ValueError:
            return web.json_response(
                {"error": f"Unsupported algorithm: {payload['algorithm']}"},
                status=422,
            )
        balancer.set_algorithm(algo)
        settings.algorithm = algo

    if "backends" in payload and payload["backends"] is not None:
        raw_backends = payload["backends"]
        if not isinstance(raw_backends, list):
            return web.json_response({"error": "backends must be a list"}, status=422)
        try:
            backend_configs = [BackendConfig.model_validate(item) for item in raw_backends]
        except ValidationError as exc:
            return web.json_response({"error": str(exc)}, status=422)
        pool.sync_pool(backend_configs)
        settings.backends = backend_configs

    if "health_check" in payload and payload["health_check"] is not None:
        try:
            hc = HealthCheckConfig.model_validate(payload["health_check"])
        except ValidationError as exc:
            return web.json_response({"error": str(exc)}, status=422)
        await health_checker.update_config(hc)
        settings.health_check = hc

    logger.info(
        "LB config hot-updated: algorithm=%s backends=%d",
        balancer.algorithm.value,
        len(pool.backends),
    )
    if health_checker.config.enabled and ("backends" in payload or "health_check" in payload):
        health_checker.trigger_probe_now()
    return await lb_status(request)


async def update_lb_algorithm(request: web.Request) -> web.Response:
    """Hot-switch LB routing algorithm."""
    denied = _authorize_admin(request)
    if denied is not None:
        return denied

    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    raw_algo = payload.get("algorithm")
    try:
        algo = LBAlgorithm(str(raw_algo))
    except ValueError:
        return web.json_response({"error": f"Unsupported algorithm: {raw_algo}"}, status=422)

    balancer = request.app[BALANCER_KEY]
    settings = request.app[SETTINGS_KEY]
    balancer.set_algorithm(algo)
    settings.algorithm = algo
    return await lb_status(request)


async def set_backend_state(request: web.Request) -> web.Response:
    """Enable or manually drain/disable a backend in the LB pool."""
    denied = _authorize_admin(request)
    if denied is not None:
        return denied

    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    identifier = str(
        payload.get("identifier") or request.match_info.get("identifier") or ""
    ).strip()
    if not identifier:
        return web.json_response({"error": "Backend identifier is required"}, status=422)
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        return web.json_response({"error": "enabled boolean is required"}, status=422)
    force = bool(payload.get("force", False))

    pool = request.app[POOL_KEY]
    try:
        backend = pool.set_backend_admin_state(identifier, enabled, force=force)
    except KeyError as exc:
        return web.json_response({"error": str(exc)}, status=404)
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=409)

    return web.json_response({"backend": backend.to_dict(), "pool": pool.stats()})


def create_app(settings: LBSettings | None = None) -> web.Application:
    """Build and configure the aiohttp Load Balancer web application."""
    if settings is None:
        settings = LBSettings()

    app = web.Application()

    pool = BackendPool.from_configs(settings.backends)
    balancer = LoadBalancer(pool=pool, algorithm=settings.algorithm)
    health_checker = ActiveHealthChecker(pool=pool, config=settings.health_check)

    app[SETTINGS_KEY] = settings
    app[POOL_KEY] = pool
    app[BALANCER_KEY] = balancer
    app[HEALTH_CHECKER_KEY] = health_checker

    async def on_startup(application: web.Application) -> None:
        session = ClientSession(
            cookie_jar=DummyCookieJar(),
            auto_decompress=False,
        )
        handler = ReverseProxyHandler(
            balancer=balancer,
            session=session,
            client_timeout_seconds=settings.client_timeout_seconds,
        )
        application[CLIENT_SESSION_KEY] = session
        application[PROXY_HANDLER_KEY] = handler

        await health_checker.start()

        logger.info(
            "SentinelX LB initialized with %d backends (algorithm=%s, health_check=%s)",
            len(settings.backends),
            balancer.algorithm.value,
            settings.health_check.enabled,
        )

    async def on_cleanup(application: web.Application) -> None:
        await health_checker.stop()

        session: ClientSession | None = application.get(CLIENT_SESSION_KEY)
        if session and not session.closed:
            await session.close()
            logger.info("Closed upstream ClientSession.")

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    # 1. Management and introspection endpoints
    app.router.add_get("/health", health_check)
    app.router.add_get("/lb/status", lb_status)
    app.router.add_put("/lb/admin/config", update_lb_config)
    app.router.add_patch("/lb/admin/algorithm", update_lb_algorithm)
    app.router.add_post("/lb/admin/backends/state", set_backend_state)
    app.router.add_post("/lb/admin/backends/{identifier}/state", set_backend_state)

    # 2. Catch-all reverse proxy route (must be added last)
    app.router.add_route("*", "/{tail:.*}", proxy_dispatcher)

    return app
