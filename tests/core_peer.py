"""Private lab traffic source. Probes one fixed target, never a caller supplied URL."""

import os

import aiohttp
from aiohttp import web


async def probe(request: web.Request) -> web.Response:
    try:
        timeout = 2 if os.getenv("CORE_PROBE_RELAY") == "1" else 0.5
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as client:
            async with client.get(os.environ["CORE_PROBE_TARGET"]) as response:
                reachable = (
                    bool((await response.json())["reachable"])
                    if os.getenv("CORE_PROBE_RELAY") == "1"
                    else response.status == 200
                )
    except (aiohttp.ClientError, TimeoutError):
        reachable = False
    return web.json_response({"reachable": reachable})


if __name__ == "__main__":
    app = web.Application()
    app.router.add_get("/probe", probe)
    web.run_app(app, host="0.0.0.0", port=8089)
