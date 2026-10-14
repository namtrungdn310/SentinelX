"""Fake metric generator for SentinelX Agent Foundation milestones."""

import math
import random
import time
from datetime import UTC, datetime

from sentinelx_common.contracts.telemetry import MetricSample


class FakeMetricGenerator:
    """Generates synthetic, deterministic/semi-random resource metrics."""

    def __init__(
        self,
        base_cpu: float = 25.0,
        base_memory: float = 40.0,
        base_disk: float = 35.0,
    ) -> None:
        self.base_cpu = base_cpu
        self.base_memory = base_memory
        self.base_disk = base_disk
        self._start_time = time.time()

    def generate_sample(self, observed_at: datetime | None = None) -> MetricSample:
        """Produce a realistic synthetic metric sample with sinusoidal wave."""
        now = observed_at or datetime.now(UTC)
        elapsed = time.time() - self._start_time

        # Generate smooth wave variation
        cpu_wave = 15.0 * math.sin(elapsed / 10.0)
        cpu_noise = random.uniform(-3.0, 3.0)
        cpu = max(1.0, min(99.0, self.base_cpu + cpu_wave + cpu_noise))

        mem_noise = random.uniform(-1.0, 1.5)
        mem = max(5.0, min(95.0, self.base_memory + mem_noise))

        rx = int(max(0, 10240 + 5120 * math.cos(elapsed / 15.0) + random.randint(-500, 500)))
        tx = int(max(0, 4096 + 2048 * math.sin(elapsed / 12.0) + random.randint(-300, 300)))

        return MetricSample(
            observed_at=now,
            cpu_percent=round(cpu, 2),
            memory_percent=round(mem, 2),
            disk_percent=round(self.base_disk, 2),
            network_rx_bytes=rx,
            network_tx_bytes=tx,
        )
