"""Correlation ID Middleware for tracing requests across the platform."""

import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from sentinelx_common.observability.logging import set_correlation_id

CORRELATION_ID_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware ensuring every HTTP request has an X-Correlation-ID header and logging context."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process request, extract or generate correlation ID, and set in context and headers."""
        incoming_id = request.headers.get(CORRELATION_ID_HEADER)
        correlation_id = (
            incoming_id.strip()
            if incoming_id and incoming_id.strip()
            else str(uuid.uuid4())
        )

        set_correlation_id(correlation_id)
        try:
            response = await call_next(request)
            response.headers[CORRELATION_ID_HEADER] = correlation_id
            return response
        finally:
            set_correlation_id(None)
