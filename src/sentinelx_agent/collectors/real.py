"""Real Linux/OS hardware resource collector for SentinelX Agent."""

import logging
from datetime import UTC, datetime
from pathlib import Path

import psutil

from sentinelx_common.contracts.telemetry import MetricSample

logger = logging.getLogger("sentinelx_agent.collectors.real")


class RealResourceCollector:
    """Non-blocking system resource collector using psutil and OS metrics."""

    def __init__(self, disk_path: str | None = None) -> None:
        self._disk_path = disk_path or self._detect_default_mount()

        # 1. Khởi tạo mốc CPU ban đầu (Priming Call) - Non-blocking interval=None
        psutil.cpu_percent(interval=None)

        # 2. Khởi tạo mốc đếm mạng để tính toán Delta
        net = psutil.net_io_counters()
        self._prev_rx_bytes: int = int(net.bytes_recv) if net else 0
        self._prev_tx_bytes: int = int(net.bytes_sent) if net else 0

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
        now = datetime.now(UTC)

        # 1. CPU Usage: Non-blocking delta calculation kể từ lần gọi trước
        cpu_raw = float(psutil.cpu_percent(interval=None))
        cpu_pct = max(0.0, min(100.0, cpu_raw))

        # 2. Memory Usage
        mem = psutil.virtual_memory()
        mem_pct = max(0.0, min(100.0, float(mem.percent)))

        # 3. Disk Usage: Tự động fallback an toàn nếu gặp lỗi phân quyền
        try:
            disk = psutil.disk_usage(self._disk_path)
            disk_pct = max(0.0, min(100.0, float(disk.percent)))
        except (PermissionError, FileNotFoundError, OSError) as err:
            logger.warning("Failed to inspect disk usage on %s: %s", self._disk_path, err)
            disk_pct = 0.0

        # 4. Network I/O Delta Calculation
        rx_delta = 0
        tx_delta = 0
        try:
            net = psutil.net_io_counters()
            if net is not None:
                current_rx = int(net.bytes_recv)
                current_tx = int(net.bytes_sent)

                # Tính độ lệch delta; nếu card mạng reboot/reset counter thì gán delta = 0
                if current_rx >= self._prev_rx_bytes:
                    rx_delta = current_rx - self._prev_rx_bytes
                if current_tx >= self._prev_tx_bytes:
                    tx_delta = current_tx - self._prev_tx_bytes

                self._prev_rx_bytes = current_rx
                self._prev_tx_bytes = current_tx
        except Exception as err:
            logger.warning("Failed to inspect network counters: %s", err)

        return MetricSample(
            observed_at=now,
            cpu_percent=round(cpu_pct, 2),
            memory_percent=round(mem_pct, 2),
            disk_percent=round(disk_pct, 2),
            network_rx_bytes=rx_delta,
            network_tx_bytes=tx_delta,
        )
