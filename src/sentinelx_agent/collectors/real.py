"""Real Linux/OS hardware resource collector for SentinelX Agent."""

import logging
from datetime import UTC, datetime
from pathlib import Path

import psutil

from sentinelx_common.contracts.telemetry import MetricSample

logger = logging.getLogger("sentinelx_agent.collectors.real")


class RealResourceCollector:
    """System metrics; call collect in a worker because CPU sampling takes 100ms."""

    def __init__(self, disk_path: str | None = None) -> None:
        self._disk_path = disk_path or self._detect_default_mount()

        self._prev_network = self._read_network()

    @staticmethod
    def _read_network() -> tuple[int, int] | None:
        try:
            net = psutil.net_io_counters()
            return (int(net.bytes_recv), int(net.bytes_sent)) if net else None
        except (OSError, psutil.Error) as err:
            logger.warning("Failed to inspect network counters: %s", err)
            return None

    @staticmethod
    def _detect_default_mount() -> str:
        """Detect default mount point across Linux, macOS, and Windows environments."""
        anchor = Path.home().anchor
        return anchor if anchor else "/"

    def collect(self) -> MetricSample:
        """Sample machine resource utilization synchronously.

        This method reads CPU, RAM, Disk, and Network IO counters.
        It is designed to be executed inside a worker thread via asyncio.to_thread.
        """
        # A bounded window is independent of thread-local previous-call state.
        cpu_raw = float(psutil.cpu_percent(interval=0.1))
        cpu_pct = max(0.0, min(100.0, cpu_raw))

        # 2. Memory Usage
        mem = psutil.virtual_memory()
        mem_pct = max(0.0, min(100.0, float(mem.percent)))

        disk_pct: float | None
        try:
            disk = psutil.disk_usage(self._disk_path)
            disk_pct = max(0.0, min(100.0, float(disk.percent)))
        except (PermissionError, FileNotFoundError, OSError) as err:
            logger.warning("Failed to inspect disk usage on %s: %s", self._disk_path, err)
            disk_pct = None

        # 4. Network I/O Delta Calculation
        rx_delta: int | None = None
        tx_delta: int | None = None
        current_network = self._read_network()
        if current_network is not None and self._prev_network is not None:
            rx_delta = max(0, current_network[0] - self._prev_network[0])
            tx_delta = max(0, current_network[1] - self._prev_network[1])
        # Rebase after a gap rather than assigning several intervals to one sample.
        self._prev_network = current_network

        return MetricSample(
            observed_at=datetime.now(UTC),
            cpu_percent=round(cpu_pct, 2),
            memory_percent=round(mem_pct, 2),
            disk_percent=round(disk_pct, 2) if disk_pct is not None else None,
            network_rx_bytes=rx_delta,
            network_tx_bytes=tx_delta,
        )
