"""Mock Backend Workload Application for SentinelX Lab.

Provides:
- Identity endpoints showing round-robin load distribution.
- Healthcheck endpoint for Load Balancer probes.
- Controllable resource stress endpoints (CPU, Memory, Latency) for testing SentinelX detection.
"""

import asyncio
import os
import socket
import time
from typing import Any
from aiohttp import web

HOSTNAME = socket.gethostname()
PORT = int(os.getenv("PORT", "8080"))
NODE_NAME = os.getenv("NODE_NAME", HOSTNAME)

REQUEST_COUNTER = 0
START_TIME = time.time()
MEMORY_HOG: list[bytes] = []


async def index_handler(request: web.Request) -> web.Response:
    """Return backend node details and request count."""
    global REQUEST_COUNTER
    REQUEST_COUNTER += 1

    return web.json_response({
        "status": "online",
        "node_name": NODE_NAME,
        "hostname": HOSTNAME,
        "client_ip": request.remote,
        "request_counter": REQUEST_COUNTER,
        "uptime_seconds": round(time.time() - START_TIME, 2),
    })


async def health_handler(_request: web.Request) -> web.Response:
    """Healthcheck endpoint for SentinelX Load Balancer."""
    return web.json_response({
        "status": "healthy",
        "node": NODE_NAME,
    })


async def cpu_stress_handler(request: web.Request) -> web.Response:
    """Simulate CPU spike for anomaly detection tests."""
    duration = float(request.query.get("duration", "5"))

    def _burn_cpu() -> None:
        stop = time.time() + duration
        while time.time() < stop:
            _ = [x * x for x in range(10_000)]

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _burn_cpu)

    return web.json_response({
        "message": f"CPU stressed for {duration} seconds on {NODE_NAME}",
        "node": NODE_NAME,
    })


async def memory_stress_handler(request: web.Request) -> web.Response:
    """Simulate Memory consumption for anomaly detection tests."""
    global MEMORY_HOG
    mb = int(request.query.get("mb", "100"))
    # Allocate approximately N MB
    MEMORY_HOG.append(b"X" * (mb * 1024 * 1024))

    return web.json_response({
        "message": f"Allocated {mb} MB RAM on {NODE_NAME}",
        "total_chunks": len(MEMORY_HOG),
        "node": NODE_NAME,
    })


async def reset_stress_handler(_request: web.Request) -> web.Response:
    """Clear memory hog allocations."""
    global MEMORY_HOG
    MEMORY_HOG.clear()
    return web.json_response({"message": "Memory allocations cleared", "node": NODE_NAME})


def create_app() -> web.Application:
    """Create web application."""
    app = web.Application()
    app.router.add_get("/", index_handler)
    app.router.add_get("/health", health_handler)
    app.router.add_post("/stress/cpu", cpu_stress_handler)
    app.router.add_post("/stress/memory", memory_stress_handler)
    app.router.add_post("/stress/reset", reset_stress_handler)
    return app


if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=PORT)
