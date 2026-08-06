"""打码效果应用。"""

from __future__ import annotations

from typing import Literal

import cv2
import numpy as np

from media_redact.detect.base import MaskRegion

MaskMode = Literal["blur", "mosaic", "solid", "none"]
MaskShape = Literal["ellipse", "polygon"]


def apply_masks(
    frame: np.ndarray,
    regions: list[MaskRegion],
    *,
    mode: MaskMode = "mosaic",
    mask_shape: MaskShape = "polygon",
    mask_scale: float = 1.0,
    mosaic_size: int = 20,
    solid_color: tuple[int, int, int] = (0, 0, 0),
) -> np.ndarray:
    """对 frame 就地打码（支持 RGB 或 BGR）。"""
    h, w = frame.shape[:2]
    for region in regions:
        scaled = region.scale_clamped(mask_scale, w, h)
        if not scaled.fully_inside(w, h):
            continue
        if len(scaled.polygon) < 3:
            continue
        _apply_single(
            frame,
            scaled,
            mode=mode,
            mask_shape=mask_shape,
            mosaic_size=mosaic_size,
            solid_color=solid_color,
        )
    return frame


def _build_replacement(
    roi: np.ndarray,
    mode: MaskMode,
    mosaic_size: int,
    solid_color: tuple[int, int, int],
) -> np.ndarray:
    if mode == "solid":
        return np.full_like(roi, solid_color)
    if mode == "blur":
        bf = 2
        bw = max(1, roi.shape[1] // bf)
        bh = max(1, roi.shape[0] // bf)
        return cv2.blur(roi, (bw, bh))
    if mode == "mosaic":
        block_w = max(1, roi.shape[1] // mosaic_size)
        block_h = max(1, roi.shape[0] // mosaic_size)
        small = cv2.resize(roi, (block_w, block_h), interpolation=cv2.INTER_LINEAR)
        return cv2.resize(small, (roi.shape[1], roi.shape[0]), interpolation=cv2.INTER_NEAREST)
    raise ValueError(f"Unknown mask mode: {mode}")


def _apply_single(
    frame: np.ndarray,
    region: MaskRegion,
    *,
    mode: MaskMode,
    mask_shape: MaskShape,
    mosaic_size: int,
    solid_color: tuple[int, int, int],
) -> None:
    if mode == "none":
        return

    x1, y1, x2, y2 = region.bounding_box()
    if x2 <= x1 or y2 <= y1:
        return

    roi = frame[y1:y2, x1:x2]
    if roi.size == 0:
        return

    replacement = _build_replacement(roi, mode, mosaic_size, solid_color)
    local_mask = np.zeros((y2 - y1, x2 - x1), dtype=np.uint8)

    if mask_shape == "ellipse":
        center = ((x2 - x1) // 2, (y2 - y1) // 2)
        axes = ((x2 - x1) // 2, (y2 - y1) // 2)
        cv2.ellipse(local_mask, center, axes, 0, 0, 360, 255, -1)
    else:
        local_polygon = np.array(
            [[x - x1, y - y1] for x, y in region.polygon],
            dtype=np.int32,
        )
        cv2.fillPoly(local_mask, [local_polygon], 255)

    mask_bool = local_mask.astype(bool)
    roi[mask_bool] = replacement[mask_bool]
