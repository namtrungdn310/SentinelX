"""Scapy/libpcap adapter; Linux opt-in, non-promiscuous, no stored packets."""

import sys
import threading
import time
from datetime import UTC, datetime
from typing import Any

from scapy.layers.inet import IP, TCP, UDP
from scapy.layers.inet6 import IPv6
from scapy.layers.l2 import Ether

from sentinelx_agent.network.aggregation import PacketObservation, SlidingWindowAggregator


def decode_packet(packet: Any) -> PacketObservation | None:
    """Extract the first IP header only; never retain packet/payload objects."""
    # Import layers before opening libpcap so Ethernet/IP dissectors are registered.
    if isinstance(packet, Ether):
        packet = packet.payload
    ip = packet
    for _ in range(8):
        if isinstance(ip, (IP, IPv6)):
            break
        ip = getattr(ip, "payload", None)
        if ip is None:
            return None
    else:
        return None
    number = int(ip.proto if isinstance(ip, IP) else ip.nh)
    protocol = {6: "tcp", 17: "udp", 1: "icmp", 58: "icmp"}.get(number, "other")
    transport = ip.payload
    destination_port = None
    flags = 0
    if isinstance(transport, (TCP, UDP)):
        destination_port = int(transport.dport)
        if isinstance(transport, TCP):
            flags = int(transport.flags)
    length = (
        (int(ip.len) if ip.len is not None else len(ip))
        if isinstance(ip, IP)
        else (40 + int(ip.plen) if ip.plen is not None else len(ip))
    )
    return PacketObservation(str(ip.src), str(ip.dst), protocol, length, destination_port, flags)


class PacketCapture:
    """Own the capture socket and sniffer thread, not the daemon's event loop."""

    def __init__(
        self, interface: str, bpf_filter: str, aggregator: SlidingWindowAggregator
    ) -> None:
        self.interface = interface
        self.bpf_filter = bpf_filter
        self.aggregator = aggregator
        self._sniffer: Any = None
        self._socket: Any = None

    def start(self) -> None:
        if sys.platform != "linux":
            raise RuntimeError("Live capture is supported only on Linux")
        from scapy.config import conf
        from scapy.sendrecv import AsyncSniffer

        conf.use_pcap = True
        if not conf.use_pcap:
            raise RuntimeError("libpcap is required for network capture")
        # Open synchronously so BPF/interface/permission errors reach the supervisor.
        self._socket = conf.L2listen(iface=self.interface, filter=self.bpf_filter, promisc=False)
        ready = threading.Event()

        def started() -> None:
            self.aggregator.begin(time.monotonic(), datetime.now(UTC))
            ready.set()

        self._sniffer = AsyncSniffer(
            opened_socket=self._socket, store=False, prn=self.observe, started_callback=started
        )
        self._sniffer.start()
        if not ready.wait(3) or not self.running:
            self.stop()
            raise RuntimeError("Capture thread did not start")

    @property
    def running(self) -> bool:
        return bool(self._sniffer is not None and self._sniffer.running)

    def observe(self, packet: Any) -> None:
        try:
            observation = decode_packet(packet)
            if observation is not None:
                self.aggregator.add(observation, time.monotonic())
        except (AttributeError, TypeError, ValueError, IndexError):
            # Malformed/truncated packets are not allowed to kill the capture loop.
            pass

    def stop(self) -> None:
        try:
            if self.running:
                self._sniffer.stop(join=True)
            elif self._sniffer is not None:
                self._sniffer.join(timeout=3)
        finally:
            if self._socket is not None:
                self._socket.close()
                self._socket = None
