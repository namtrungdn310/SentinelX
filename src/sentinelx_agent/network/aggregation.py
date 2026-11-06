"""Bounded overlapping windows; packet bodies never enter aggregator state."""

import math
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sentinelx_common.contracts.network import NetworkFeature, NetworkWindow


@dataclass(frozen=True)
class PacketObservation:
    source_ip: str
    destination_ip: str
    protocol: str
    byte_count: int
    destination_port: int | None = None
    tcp_flags: int = 0


@dataclass
class Counters:
    packets: int = 0
    bytes: int = 0
    syn: int = 0
    ack: int = 0
    rst: int = 0
    fin: int = 0
    ports: set[int] = field(default_factory=set)
    truncated: bool = False


@dataclass
class WindowState:
    groups: dict[tuple[str, str, str], Counters] = field(default_factory=dict)
    omitted: int = 0


class SlidingWindowAggregator:
    """Monotonic anchored windows, bounded cardinality, callback/thread safe.

    A packet contributes to window/step overlapping windows. No connection
    reassembly or packet timestamp sorting; the clock measures local receipt.
    """

    def __init__(
        self,
        interface: str,
        *,
        window_seconds: int = 10,
        step_seconds: int = 5,
        max_groups: int = 1024,
        start_monotonic: float,
        start_utc: datetime,
    ) -> None:
        if (
            not 1 <= step_seconds <= window_seconds <= 300
            or window_seconds % step_seconds
            or window_seconds // step_seconds > 12
            or not 1 <= max_groups <= 1024
        ):
            raise ValueError("Invalid window/step/cardinality settings")
        self.interface = interface
        self.window = window_seconds
        self.step = step_seconds
        self.max_groups = max_groups
        self._mono = start_monotonic
        self._utc = start_utc.astimezone(UTC)
        self._states: dict[int, WindowState] = {}
        self._next_end = window_seconds
        self._skipped = 0
        self._lock = threading.Lock()

    def begin(self, monotonic: float, utc: datetime) -> None:
        """Anchor at sniffer readiness, excluding library/socket startup time."""
        with self._lock:
            self._mono = monotonic
            self._utc = utc.astimezone(UTC)
            self._states.clear()
            self._next_end = self.window
            self._skipped = 0

    def _bound_history(self, elapsed: float) -> None:
        oldest_end = max(self.window, math.floor(elapsed / self.step) * self.step - 15 * self.step)
        if self._next_end < oldest_end:
            self._skipped += (oldest_end - self._next_end) // self.step
            self._next_end = oldest_end
            for start in list(self._states):
                if start + self.window < self._next_end:
                    del self._states[start]

    def add(self, packet: PacketObservation, now: float) -> None:
        elapsed = max(0, now - self._mono)
        latest = math.floor(elapsed / self.step) * self.step
        key = (packet.source_ip, packet.destination_ip, packet.protocol)
        with self._lock:
            self._bound_history(elapsed)
            for start in range(max(0, latest - self.window + self.step), latest + 1, self.step):
                if start + self.window < self._next_end:
                    continue
                state = self._states.setdefault(start, WindowState())
                counter = state.groups.get(key)
                if counter is None:
                    if len(state.groups) >= self.max_groups:
                        state.omitted += 1
                        continue
                    counter = state.groups[key] = Counters()
                counter.packets += 1
                counter.bytes += packet.byte_count
                if packet.protocol == "tcp":
                    counter.syn += bool(packet.tcp_flags & 0x02)
                    counter.ack += bool(packet.tcp_flags & 0x10)
                    counter.rst += bool(packet.tcp_flags & 0x04)
                    counter.fin += bool(packet.tcp_flags & 0x01)
                if packet.destination_port is not None:
                    if len(counter.ports) < 64 or packet.destination_port in counter.ports:
                        counter.ports.add(packet.destination_port)
                    else:
                        counter.truncated = True

    def drain(self, now: float) -> list[NetworkWindow]:
        """Drain completed windows; bound catch-up after a delayed scheduler."""
        elapsed = max(0, now - self._mono)
        result: list[NetworkWindow] = []
        with self._lock:
            self._bound_history(elapsed)
            while self._next_end <= elapsed and len(result) < 16:
                start = self._next_end - self.window
                state = self._states.pop(start, WindowState())
                features = [
                    NetworkFeature.model_validate(
                        {
                            "source_ip": src,
                            "destination_ip": dst,
                            "protocol": protocol,
                            "packet_count": c.packets,
                            "byte_count": c.bytes,
                            "syn_count": c.syn,
                            "ack_count": c.ack,
                            "rst_count": c.rst,
                            "fin_count": c.fin,
                            "destination_ports": sorted(c.ports),
                            "ports_truncated": c.truncated,
                        }
                    )
                    for (src, dst, protocol), c in sorted(state.groups.items())
                ]
                result.append(
                    NetworkWindow(
                        window_id=uuid4(),
                        window_start=self._utc + timedelta(seconds=start),
                        window_end=self._utc + timedelta(seconds=self._next_end),
                        interface=self.interface,
                        features=features,
                        omitted_packets=state.omitted,
                        skipped_windows=self._skipped,
                    )
                )
                self._skipped = 0
                self._next_end += self.step
        return result
