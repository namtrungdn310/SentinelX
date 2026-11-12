"""SYN Flood detection based on TCP flag asymmetry and volume."""

import uuid

from sentinelx_common.contracts.detection import (
    DetectionEventContract,
    DetectionSeverity,
    DetectorType,
    NetworkAnomalyDetail,
)
from sentinelx_common.contracts.network import NetworkWindow
from sentinelx_controller.modules.detection.detectors.network_base import BaseNetworkDetector


class SynFloodDetector(BaseNetworkDetector):
    """Detector identifying TCP SYN Flood DoS/DDoS attacks."""

    def __init__(self, min_syn: int = 50, syn_ack_ratio: float = 3.0) -> None:
        self.min_syn = min_syn
        self.syn_ack_ratio = syn_ack_ratio

    @property
    def name(self) -> str:
        return DetectorType.SYN_FLOOD.value

    def evaluate(
        self,
        node_id: uuid.UUID,
        window: NetworkWindow,
    ) -> list[DetectionEventContract]:
        events: list[DetectionEventContract] = []
        for feature in window.features:
            if feature.protocol != "tcp":
                continue

            ack_divisor = max(feature.ack_count, 1)
            ratio = feature.syn_count / ack_divisor
            is_unbalanced = (feature.ack_count == 0) or (ratio >= self.syn_ack_ratio)

            if feature.syn_count >= self.min_syn and is_unbalanced:
                severity = (
                    DetectionSeverity.CRITICAL
                    if feature.syn_count >= 200
                    or (feature.syn_count >= 100 and feature.ack_count == 0)
                    else DetectionSeverity.HIGH
                )
                confidence = 0.98 if feature.ack_count == 0 else min(0.95, 0.85 + (ratio * 0.01))

                event = DetectionEventContract(
                    node_id=str(node_id),
                    detector_name=self.name,
                    severity=severity,
                    attacker_ip=str(feature.source_ip),
                    confidence_score=round(confidence, 2),
                    details=NetworkAnomalyDetail(
                        attack_type="SYN_FLOOD",
                        source_ip=str(feature.source_ip),
                        destination_ip=str(feature.destination_ip),
                        protocol="tcp",
                        packet_count=feature.packet_count,
                        byte_count=feature.byte_count,
                        syn_count=feature.syn_count,
                        ack_count=feature.ack_count,
                        targeted_ports=feature.destination_ports,
                        metric_ratio=round(ratio, 2),
                        extra_context={
                            "interface": window.interface,
                            "window_id": str(window.window_id),
                        },
                    ),
                    detected_at=window.window_end,
                )
                events.append(event)

        return events
