"""Port scan reconnaissance detection."""

import uuid

from sentinelx_common.contracts.detection import (
    DetectionEventContract,
    DetectionSeverity,
    DetectorType,
    NetworkAnomalyDetail,
)
from sentinelx_common.contracts.network import NetworkWindow
from sentinelx_controller.modules.detection.detectors.network_base import BaseNetworkDetector


class PortScanDetector(BaseNetworkDetector):
    """Detector identifying horizontal and vertical port scanning reconnaissance."""

    def __init__(self, port_threshold: int = 15) -> None:
        self.port_threshold = port_threshold

    @property
    def name(self) -> str:
        return DetectorType.PORT_SCAN.value

    def evaluate(
        self,
        node_id: uuid.UUID,
        window: NetworkWindow,
    ) -> list[DetectionEventContract]:
        events: list[DetectionEventContract] = []
        for feature in window.features:
            ports_count = len(feature.destination_ports)
            if ports_count >= self.port_threshold or feature.ports_truncated:
                severity = (
                    DetectionSeverity.HIGH
                    if ports_count >= 30 or feature.ports_truncated
                    else DetectionSeverity.MEDIUM
                )
                confidence = (
                    0.95
                    if feature.ports_truncated
                    else min(0.92, 0.80 + (ports_count * 0.005))
                )

                event = DetectionEventContract(
                    node_id=str(node_id),
                    detector_name=self.name,
                    severity=severity,
                    attacker_ip=str(feature.source_ip),
                    confidence_score=round(confidence, 2),
                    details=NetworkAnomalyDetail(
                        attack_type="PORT_SCAN",
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
                            "ports_scanned_count": ports_count,
                            "ports_truncated": feature.ports_truncated,
                        },
                    ),
                    detected_at=window.window_end,
                )
                events.append(event)

        return events
