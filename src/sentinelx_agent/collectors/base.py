"""Base protocol definition for SentinelX Agent metric collectors."""

from typing import Protocol, runtime_checkable

from sentinelx_common.contracts.telemetry import MetricSample


@runtime_checkable
class MetricCollector(Protocol):
    """Protocol for machine resource metric collectors."""

    def collect(self) -> MetricSample:
        """Sample and produce a MetricSample at the current moment."""
        ...
