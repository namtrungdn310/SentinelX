"""Abstract base class for network anomaly detectors."""

import uuid
from abc import ABC, abstractmethod

from sentinelx_common.contracts.detection import DetectionEventContract
from sentinelx_common.contracts.network import NetworkWindow


class BaseNetworkDetector(ABC):
    """Base interface for all network anomaly detectors (Milestone M4)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tên định danh duy nhất của bộ network detector."""
        ...

    @abstractmethod
    def evaluate(
        self,
        node_id: uuid.UUID,
        window: NetworkWindow,
    ) -> list[DetectionEventContract]:
        """Đánh giá một cửa sổ mạng NetworkWindow để phát hiện hành vi tấn công/bất thường.

        Args:
            node_id: UUID của Node bị nhắm tới.
            window: Cửa sổ quan sát mạng chứa các NetworkFeature gộp.

        Returns:
            Danh sách các DetectionEventContract phát hiện được (mỗi phần tử kèm attacker_ip).
        """
        ...

