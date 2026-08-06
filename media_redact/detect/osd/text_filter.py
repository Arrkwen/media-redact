"""OSD 文字框过滤。"""

from __future__ import annotations

import re
from dataclasses import dataclass

import cv2
import numpy as np

from media_redact.detect.base import MaskRegion


@dataclass
class TextFilterConfig:
    patterns: list[str] | None = None


class TextRegionFilter:
    """正则匹配（识别文本）。"""

    def __init__(self, config: TextFilterConfig | None = None) -> None:
        self.config = config or TextFilterConfig()
        self._patterns = [re.compile(pattern) for pattern in (self.config.patterns or [])]

    def matches_text(self, text: str) -> bool:
        if not self._patterns:
            return False
        return any(pattern.search(text) for pattern in self._patterns)


def boxes_to_mask_regions(
    boxes: np.ndarray,
    scores: list[float],
    *,
    offset_x: int = 0,
    offset_y: int = 0,
    label_prefix: str = "osd_text",
) -> list[MaskRegion]:
    regions: list[MaskRegion] = []
    for index, (box, score) in enumerate(zip(boxes, scores, strict=False)):
        polygon = [(int(x + offset_x), int(y + offset_y)) for x, y in box.reshape(-1, 2)]
        if len(polygon) < 3:
            continue
        if not cv2.isContourConvex(np.array(polygon, dtype=np.int32)):
            polygon = _ensure_quad(polygon)
        regions.append(
            MaskRegion(
                polygon=polygon,
                score=float(score),
                label=f"{label_prefix}_{index}",
            )
        )
    return regions


def _ensure_quad(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    arr = np.array(points, dtype=np.float32).reshape(-1, 1, 2)
    rect = cv2.minAreaRect(arr)
    box = cv2.boxPoints(rect)
    return [(int(x), int(y)) for x, y in box]
