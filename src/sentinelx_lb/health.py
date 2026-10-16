"""Active background health checking daemon for SentinelX Load Balancer."""

import asyncio
import logging

from aiohttp import ClientError, ClientSession, ClientTimeout

from sentinelx_lb.config import HealthCheckConfig
from sentinelx_lb.pool import Backend, BackendPool

logger = logging.getLogger("sentinelx_lb.health")


class ActiveHealthChecker:
    """Proactively probes upstream backends to eject dead nodes and re-add recovered ones."""

    def __init__(
        self,
        pool: BackendPool,
        config: HealthCheckConfig,
        session: ClientSession | None = None,
    ) -> None:
        self.pool = pool
        self.config = config
        self._session = session
        self._owns_session = session is None
        self._task: asyncio.Task[None] | None = None
        self._stopped = False

    async def probe_backend(self, backend: Backend) -> None:
        """Send a single active health probe to a backend and update its state machine."""
        if self._session is None or self._session.closed:
            return

        probe_path = backend.health_path or self.config.path
        target_url = f"{backend.url}{probe_path}"
        timeout = ClientTimeout(total=self.config.timeout_seconds)

        try:
            async with self._session.get(
                target_url, timeout=timeout, allow_redirects=False
            ) as resp:
                status_code = resp.status
                if 200 <= status_code < 400:
                    re_added = backend.record_health_success(
                        success_threshold=self.config.success_threshold,
                        status_code=status_code,
                    )
                    if re_added:
                        logger.info(
                            "HealthCheck: Backend '%s' (%s) recovered -> RE-ADDED (status=%s)",
                            backend.name,
                            backend.url,
                            backend.health_state.value,
                        )
                else:
                    err_msg = f"HTTP {status_code}"
                    ejected = backend.record_health_failure(
                        failure_threshold=self.config.failure_threshold,
                        error_msg=err_msg,
                        status_code=status_code,
                    )
                    if ejected:
                        logger.warning(
                            "HealthCheck: Backend '%s' (%s) probe failed (%s) -> EJECTED",
                            backend.name,
                            backend.url,
                            err_msg,
                        )

        except TimeoutError:
            err_msg = f"Timed out after {self.config.timeout_seconds}s"
            ejected = backend.record_health_failure(
                failure_threshold=self.config.failure_threshold,
                error_msg=err_msg,
                status_code=None,
            )
            if ejected:
                logger.warning(
                    "HealthCheck: Backend '%s' (%s) timed out -> EJECTED from pool",
                    backend.name,
                    backend.url,
                )

        except ClientError as exc:
            err_msg = f"Connection error: {exc}"
            ejected = backend.record_health_failure(
                failure_threshold=self.config.failure_threshold,
                error_msg=err_msg,
                status_code=None,
            )
            if ejected:
                logger.warning(
                    "HealthCheck: Backend '%s' (%s) connection failed -> EJECTED: %s",
                    backend.name,
                    backend.url,
                    exc,
                )

        except Exception as exc:
            logger.error("HealthCheck: Unexpected error probing backend %s: %s", backend.url, exc)
            backend.record_health_failure(
                failure_threshold=self.config.failure_threshold,
                error_msg=str(exc),
                status_code=None,
            )

    async def probe_all(self) -> None:
        """Probe all backends in the pool concurrently."""
        if not self.pool.backends:
            return

        tasks = [self.probe_backend(backend) for backend in self.pool.backends]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _loop(self) -> None:
        """Periodic background probing loop."""
        logger.info(
            "ActiveHealthChecker started (interval=%.1fs, path=%s, fail=%d, succ=%d)",
            self.config.interval_seconds,
            self.config.path,
            self.config.failure_threshold,
            self.config.success_threshold,
        )
        while not self._stopped:
            try:
                await self.probe_all()
            except Exception as exc:
                logger.error("Error in health checker probe cycle: %s", exc)

            try:
                await asyncio.sleep(self.config.interval_seconds)
            except asyncio.CancelledError:
                break

    async def start(self) -> None:
        """Start the background health checker daemon."""
        if not self.config.enabled:
            logger.info("Active health checking is disabled in configuration.")
            return

        self._stopped = False
        if self._session is None or self._session.closed:
            self._session = ClientSession()
            self._owns_session = True

        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        """Stop the background loop and close any owned HTTP sessions."""
        self._stopped = True
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()
            self._session = None

        logger.info("ActiveHealthChecker stopped.")
