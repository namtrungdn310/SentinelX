"""Abstract base class for resource anomaly detectors."""

import uuid
from abc import ABC, abstractmethod

from sentinelx_common.contracts.detection import DetectionEventContract
from sentinelx_common.contracts.telemetry import MetricSample


class BaseDetector(ABC):
    """Base interface for all telemetry and resource detectors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tên định danh duy nhất của bộ detector."""
        ...

    @abstractmethod
    def evaluate(
        self,
        node_id: uuid.UUID,
        window_samples: list[MetricSample],
    ) -> DetectionEventContract | None:
        """Đánh giá cửa sổ trượt các mẫu metric để tìm bất thường.

        Args:
            node_id: UUID của Node đang được theo dõi.
            window_samples: Danh sách mẫu metric gần nhất theo thứ tự thời gian.

        Returns:
            DetectionEventContract nếu phát hiện bất thường, ngược lại trả về None.
        """
        ...
