"""从检测框裁剪文字行图像。"""

from __future__ import annotations

import cv2
import numpy as np

from media_redact.detect.base import MaskRegion


def crop_text_region(image: np.ndarray, region: MaskRegion, *, padding: int = 2) -> np.ndarray | None:
    """按检测框 bounding box 裁剪 BGR 子图。"""
    x1, y1, x2, y2 = region.bounding_box()
    height, width = image.shape[:2]
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(width, x2 + padding)
    y2 = min(height, y2 + padding)
    if x2 <= x1 or y2 <= y1:
        return None
    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    return crop


def crop_text_region_perspective(image: np.ndarray, region: MaskRegion) -> np.ndarray | None:
    """按四边形透视裁剪，适合轻微倾斜文字。"""
    points = np.array(region.polygon, dtype=np.float32)
    if len(points) < 4:
        return crop_text_region(image, region)

    width_a = np.linalg.norm(points[0] - points[1])
    width_b = np.linalg.norm(points[2] - points[3])
    height_a = np.linalg.norm(points[0] - points[3])
    height_b = np.linalg.norm(points[1] - points[2])
    crop_width = int(max(width_a, width_b))
    crop_height = int(max(height_a, height_b))
    if crop_width < 2 or crop_height < 2:
        return crop_text_region(image, region)

    dst = np.array(
        [[0, 0], [crop_width, 0], [crop_width, crop_height], [0, crop_height]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(
        points[:4].astype(np.float32),
        dst,
    )
    return cv2.warpPerspective(image, matrix, (crop_width, crop_height))
