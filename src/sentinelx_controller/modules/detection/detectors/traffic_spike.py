"""Traffic spike and volumetric flooding detection."""

import uuid

from sentinelx_common.contracts.detection import (
    DetectionEventContract,
    DetectionSeverity,
    DetectorType,
    NetworkAnomalyDetail,
)
from sentinelx_common.contracts.network import NetworkWindow
from sentinelx_controller.modules.detection.detectors.network_base import BaseNetworkDetector


class TrafficSpikeDetector(BaseNetworkDetector):
    """Detector identifying volumetric packet spikes and UDP flood attacks."""

    def __init__(
        self,
        packet_threshold: int = 1000,
        byte_threshold: int = 5_000_000,
        udp_threshold: int = 300,
    ) -> None:
        self.packet_threshold = packet_threshold
        self.byte_threshold = byte_threshold
        self.udp_threshold = udp_threshold

    @property
    def name(self) -> str:
        return DetectorType.TRAFFIC_SPIKE.value

    def evaluate(
        self,
        node_id: uuid.UUID,
        window: NetworkWindow,
    ) -> list[DetectionEventContract]:
        events: list[DetectionEventContract] = []
        for feature in window.features:
            if feature.direction == "outbound":
                continue
            scale = 10 / (window.window_end - window.window_start).total_seconds()
            packets = feature.packet_count * scale
            byte_count = feature.byte_count * scale
            is_udp_flood = feature.protocol == "udp" and packets >= self.udp_threshold
            is_volumetric_spike = (
                packets >= self.packet_threshold or byte_count >= self.byte_threshold
            )

            if is_udp_flood or is_volumetric_spike:
                severity = (
                    DetectionSeverity.CRITICAL
                    if packets >= 2000 or byte_count >= 10_000_000
                    else DetectionSeverity.HIGH
                )
                confidence = 0.92 if is_udp_flood else 0.85

                event = DetectionEventContract(
                    node_id=str(node_id),
                    detector_name=self.name,
                    severity=severity,
                    attacker_ip=str(feature.source_ip),
                    confidence_score=round(confidence, 2),
                    details=NetworkAnomalyDetail(
                        attack_type="UDP_FLOOD" if is_udp_flood else "TRAFFIC_SPIKE",
                        source_ip=str(feature.source_ip),
                        destination_ip=str(feature.destination_ip),
                        protocol=feature.protocol,
                        packet_count=feature.packet_count,
                        byte_count=feature.byte_count,
                        syn_count=feature.syn_count,
                        ack_count=feature.ack_count,
                        targeted_ports=feature.destination_ports,
                        extra_context={
                            "interface": window.interface,
                            "window_id": str(window.window_id),
                            "is_udp_flood": is_udp_flood,
                            "direction": feature.direction,
                            "packets_per_second": packets / 10,
                            "bytes_per_second": byte_count / 10,
                        },
                    ),
                    detected_at=window.window_end,
                )
                events.append(event)

        return events
