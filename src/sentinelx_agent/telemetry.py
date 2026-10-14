"""Telemetry batching and buffer management for Agent."""

from collections import deque

from sentinelx_common.contracts.telemetry import MetricSample


class TelemetryBatcher:
    """In-memory buffer for collecting and flushing metric sample batches."""

    def __init__(self, max_buffer_size: int = 1000) -> None:
        self._max_buffer_size = max_buffer_size
        self._buffer: deque[MetricSample] = deque(maxlen=max_buffer_size)

    def add(self, sample: MetricSample) -> None:
        """Add a metric sample into the buffer."""
        self._buffer.append(sample)

    def drain(self, max_count: int | None = None) -> list[MetricSample]:
        """Drain up to max_count samples from the buffer (oldest first)."""
        count = len(self._buffer) if max_count is None else min(len(self._buffer), max_count)
        result: list[MetricSample] = []
        for _ in range(count):
            result.append(self._buffer.popleft())
        return result

    def is_ready(self, batch_size: int) -> bool:
        """Check if buffer has accumulated at least batch_size samples."""
        return len(self._buffer) >= batch_size

    def __len__(self) -> int:
        return len(self._buffer)
