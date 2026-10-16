"""HTTP Reverse Proxy engine for SentinelX Load Balancer."""

import logging
from collections.abc import Mapping

from aiohttp import ClientError, ClientSession, ClientTimeout, web

from sentinelx_lb.balancer import LoadBalancer

logger = logging.getLogger("sentinelx_lb.proxy")

# RFC 7230 §6.1 / RFC 2616 §13.5.1: Hop-by-hop headers that must not be forwarded by a proxy
HOP_BY_HOP_HEADERS: frozenset[str] = frozenset({
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
})


def filter_forward_headers(request: web.Request) -> dict[str, str]:
    """Strip hop-by-hop headers and inject standard X-Forwarded-* headers."""
    headers = {
        key: val
        for key, val in request.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }

    client_ip = request.remote or "unknown"
    existing_xff = request.headers.get("X-Forwarded-For")
    headers["X-Forwarded-For"] = f"{existing_xff}, {client_ip}" if existing_xff else client_ip
    headers["X-Forwarded-Proto"] = request.scheme
    headers["X-Forwarded-Host"] = request.host

    return headers


def filter_response_headers(upstream_headers: Mapping[str, str]) -> dict[str, str]:
    """Filter upstream response headers before relaying back to the client."""
    return {
        key: val
        for key, val in upstream_headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }


class ReverseProxyHandler:
    """Dispatches incoming client HTTP traffic to chosen upstream backend with streaming."""

    def __init__(
        self,
        balancer: LoadBalancer,
        session: ClientSession,
        client_timeout_seconds: float = 30.0,
    ) -> None:
        self.balancer = balancer
        self.session = session
        self.client_timeout_seconds = client_timeout_seconds

    async def handle_proxy(self, request: web.Request) -> web.StreamResponse:
        """Route client request to the selected upstream backend."""
        backend = self.balancer.select_backend()
        if backend is None:
            return web.json_response(
                {
                    "error": "Service Unavailable",
                    "message": "No healthy upstream backends available in pool",
                },
                status=503,
            )

        # 1. Acquire in-flight slot
        backend.acquire()
        status_code: int = 502
        is_error: bool = False

        try:
            target_url = f"{backend.url}{request.rel_url}"
            fwd_headers = filter_forward_headers(request)
            body = await request.read()
            timeout = ClientTimeout(total=self.client_timeout_seconds)

            async with self.session.request(
                method=request.method,
                url=target_url,
                headers=fwd_headers,
                data=body,
                timeout=timeout,
                allow_redirects=False,
            ) as upstream_resp:
                status_code = upstream_resp.status
                resp_headers = filter_response_headers(upstream_resp.headers)

                # Initialize stream back to client
                client_resp = web.StreamResponse(status=status_code, headers=resp_headers)
                await client_resp.prepare(request)

                # Stream response payload in 64KB chunks
                async for chunk in upstream_resp.content.iter_chunked(65536):
                    await client_resp.write(chunk)

                await client_resp.write_eof()
                return client_resp

        except TimeoutError:
            is_error = True
            status_code = 504
            logger.warning("Gateway timeout connecting to upstream backend: %s", backend.url)
            return web.json_response(
                {
                    "error": "Gateway Timeout",
                    "message": (
                        f"Upstream backend {backend.name} timed out "
                        f"after {self.client_timeout_seconds}s"
                    ),
                    "upstream": backend.url,
                },
                status=504,
            )

        except ClientError as exc:
            is_error = True
            status_code = 502
            logger.warning("Bad gateway error contacting upstream %s: %s", backend.url, exc)
            return web.json_response(
                {
                    "error": "Bad Gateway",
                    "message": f"Failed to connect to upstream backend {backend.name}",
                    "upstream": backend.url,
                    "detail": str(exc),
                },
                status=502,
            )

        except Exception as exc:
            is_error = True
            status_code = 502
            logger.error("Unexpected error proxying to upstream %s: %s", backend.url, exc)
            return web.json_response(
                {
                    "error": "Bad Gateway",
                    "message": "Internal error proxying request to upstream",
                    "upstream": backend.url,
                },
                status=502,
            )

        finally:
            # 2. Guarantee release in-flight slot
            backend.release(status_code=status_code, is_error=is_error)
