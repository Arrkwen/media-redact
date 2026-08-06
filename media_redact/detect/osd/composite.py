"""组合多种 OSD 检测器。"""

from __future__ import annotations

from typing import Protocol

import numpy as np

from media_redact.detect.base import MaskRegion
from media_redact.detect.osd.region import RegionOSDDetector
from media_redact.detect.osd.text_detector import TextOSDDetector


class OSDDetector(Protocol):
    def detect(self, image: np.ndarray) -> list[MaskRegion]: ...


class CompositeOSDDetector:
    """合并固定区域与文字检测。"""

    def __init__(
        self,
        *,
        region_detector: RegionOSDDetector | None = None,
        text_detector: TextOSDDetector | None = None,
    ) -> None:
        if region_detector is None and text_detector is None:
            raise ValueError("At least one OSD detector is required.")
        self.region_detector = region_detector
        self.text_detector = text_detector

    @classmethod
    def from_parts(
        cls,
        *,
        region_specs: list[str] | None = None,
        text_detector: TextOSDDetector | None = None,
    ) -> CompositeOSDDetector:
        region_detector = None
        if region_specs:
            region_detector = RegionOSDDetector.from_specs(region_specs)
        return cls(region_detector=region_detector, text_detector=text_detector)

    def detect(self, image: np.ndarray) -> list[MaskRegion]:
        regions: list[MaskRegion] = []
        if self.region_detector is not None:
            regions.extend(self.region_detector.detect(image))
        if self.text_detector is not None:
            regions.extend(self.text_detector.detect(image))
        return regions
