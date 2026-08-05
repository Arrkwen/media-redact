"""单帧打码处理器。"""

from __future__ import annotations

import cv2
import numpy as np

from media_redact.config import RedactConfig
from media_redact.detect.base import MaskRegion
from media_redact.detect.face import FaceDetector
from media_redact.detect.osd import RegionOSDDetector
from media_redact.mask.applicator import apply_masks


class RedactProcessor:
    """检测 + 打码的单帧处理器。"""

    def __init__(
        self,
        config: RedactConfig,
        face_detector: FaceDetector | None = None,
        osd_detector: RegionOSDDetector | None = None,
    ) -> None:
        self.config = config
        self.face_detector = face_detector
        self.osd_detector = osd_detector

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        对单帧打码。

        Args:
            frame: RGB uint8 图像 (H, W, 3)，与 imageio 读取格式一致
        """
        bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        face_regions: list[MaskRegion] = []
        osd_regions: list[MaskRegion] = []

        if self.config.face_enabled and self.face_detector is not None:
            face_regions = self.face_detector.detect(bgr)

        if self.config.osd_enabled and self.osd_detector is not None:
            osd_regions = self.osd_detector.detect(bgr)

        common_kwargs = {
            "mode": self.config.mask,
            "mask_shape": self.config.mask_shape,
            "mosaic_size": self.config.mosaic_size,
        }

        if face_regions:
            apply_masks(
                frame,
                face_regions,
                mask_scale=self.config.mask_scale,
                **common_kwargs,
            )

        if osd_regions:
            apply_masks(
                frame,
                osd_regions,
                mask_scale=1.0,
                **common_kwargs,
            )

        return frame
