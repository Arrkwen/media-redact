"""OSD 文字框过滤。"""

from __future__ import annotations

import re
from dataclasses import dataclass

import cv2
import numpy as np

from media_redact.detect.base import MaskRegion


@dataclass
class TextFilterConfig:
    min_height_ratio: float = 0.008
    max_height_ratio: float = 0.12
    min_width_ratio: float = 0.02
    max_width_ratio: float = 0.95
    min_aspect: float = 0.15
    max_aspect: float = 25.0
    patterns: list[str] | None = None


class TextRegionFilter:
    """几何过滤 + 正则匹配（识别文本）。"""

    def __init__(self, config: TextFilterConfig | None = None) -> None:
        self.config = config or TextFilterConfig()
        self._patterns = [re.compile(pattern) for pattern in (self.config.patterns or [])]

    def filter_geometry(self, image: np.ndarray, regions: list[MaskRegion]) -> list[MaskRegion]:
        if not regions:
            return []
        height, width = image.shape[:2]
        return [region for region in regions if self._passes_geometry(region, width, height)]

    def matches_text(self, text: str) -> bool:
        if not self._patterns:
            return False
        return any(pattern.search(text) for pattern in self._patterns)

    def _passes_geometry(
        self,
        region: MaskRegion,
        image_width: int,
        image_height: int,
    ) -> bool:
        x1, y1, x2, y2 = region.bounding_box()
        box_w = max(1, x2 - x1)
        box_h = max(1, y2 - y1)
        width_ratio = box_w / image_width
        height_ratio = box_h / image_height
        aspect = box_w / box_h
        cfg = self.config
        if height_ratio < cfg.min_height_ratio or height_ratio > cfg.max_height_ratio:
            return False
        if width_ratio < cfg.min_width_ratio or width_ratio > cfg.max_width_ratio:
            return False
        if aspect < cfg.min_aspect or aspect > cfg.max_aspect:
            return False
        return True


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
