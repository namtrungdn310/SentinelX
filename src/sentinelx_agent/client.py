"""Asynchronous HTTP client for Agent to Controller communication."""

import logging
from typing import Any

import aiohttp

from sentinelx_common.contracts.agents import (
    AgentEnrollRequest,
    AgentEnrollResponse,
    HeartbeatRequest,
    HeartbeatResponse,
)
from sentinelx_common.contracts.telemetry import (
    MetricBatchRequest,
    MetricBatchResponse,
)

logger = logging.getLogger("sentinelx_agent.client")


class ControllerClientError(Exception):
    """Exception raised when Controller returns an error response."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"Controller request failed [HTTP {status_code}]: {message}")


class ControllerClient:
    """Async HTTP client communicating with SentinelX Controller."""

    def __init__(
        self,
        controller_url: str,
        timeout_seconds: float = 5.0,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._base_url = controller_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._session = session
        self._owns_session = session is None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or (
            isinstance(self._session, aiohttp.ClientSession) and self._session.closed
        ):
            self._session = aiohttp.ClientSession(timeout=self._timeout)
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close active HTTP session."""
        if (
            self._owns_session
            and isinstance(self._session, aiohttp.ClientSession)
            and not self._session.closed
        ):
            await self._session.close()


    async def __aenter__(self) -> "ControllerClient":
        await self._get_session()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        await self.close()

    async def enroll(self, request: AgentEnrollRequest) -> AgentEnrollResponse:
        """Send enrollment request to Controller."""
        url = f"{self._base_url}/api/v1/nodes/enroll"
        session = await self._get_session()

        payload = request.model_dump(mode="json")
        logger.info("Enrolling node with Controller at: %s", url)

        async with session.post(url, json=payload) as resp:
            data = await resp.json()
            if resp.status != 200:
                detail = data.get("detail", str(data)) if isinstance(data, dict) else str(data)
                raise ControllerClientError(status_code=resp.status, message=detail)

            return AgentEnrollResponse.model_validate(data)

    async def send_heartbeat(self, request: HeartbeatRequest) -> HeartbeatResponse:
        """Send heartbeat message to Controller."""
        url = f"{self._base_url}/api/v1/nodes/heartbeat"
        session = await self._get_session()

        payload = request.model_dump(mode="json")
        logger.debug("Sending heartbeat to %s (sequence=%d)", url, request.sequence)

        async with session.post(url, json=payload) as resp:
            data = await resp.json()
            if resp.status != 200:
                detail = data.get("detail", str(data)) if isinstance(data, dict) else str(data)
                raise ControllerClientError(status_code=resp.status, message=detail)

            return HeartbeatResponse.model_validate(data)

    async def send_metrics(self, request: MetricBatchRequest) -> MetricBatchResponse:
        """Send a batch of metric samples to Controller."""
        url = f"{self._base_url}/api/v1/telemetry/metrics"
        session = await self._get_session()

        payload = request.model_dump(mode="json")
        logger.debug(
            "Sending metric batch to %s (sequence=%d, count=%d)",
            url,
            request.sequence,
            len(request.samples),
        )

        async with session.post(url, json=payload) as resp:
            data = await resp.json()
            if resp.status != 200:
                detail = data.get("detail", str(data)) if isinstance(data, dict) else str(data)
                raise ControllerClientError(status_code=resp.status, message=detail)

            return MetricBatchResponse.model_validate(data)

