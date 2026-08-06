"""PP-OCRv5 文字检测预处理。"""

from __future__ import annotations

import cv2
import numpy as np


class TextDetPreprocess:
    """PP-OCRv5 mobile det 预处理。"""

    def __init__(
        self,
        *,
        limit_side_len: int = 736,
        limit_type: str = "min",
        mean: tuple[float, float, float] = (0.5, 0.5, 0.5),
        std: tuple[float, float, float] = (0.5, 0.5, 0.5),
    ) -> None:
        self.limit_side_len = limit_side_len
        self.limit_type = limit_type
        self.mean = np.array(mean, dtype=np.float32)
        self.std = np.array(std, dtype=np.float32)

    def resolve_limit_side_len(self, image: np.ndarray) -> int:
        if self.limit_type == "min":
            return self.limit_side_len
        max_wh = max(image.shape[0], image.shape[1])
        if max_wh < 960:
            return 960
        if max_wh < 1500:
            return 1500
        return 2000

    def __call__(self, image: np.ndarray) -> np.ndarray:
        limit_side_len = self.resolve_limit_side_len(image)
        resized = self._resize(image, limit_side_len)
        normalized = ((resized.astype(np.float32) / 255.0) - self.mean) / self.std
        chw = normalized.transpose(2, 0, 1)
        return np.expand_dims(chw, axis=0).astype(np.float32)

    def _resize(self, image: np.ndarray, limit_side_len: int) -> np.ndarray:
        height, width = image.shape[:2]
        if self.limit_type == "max":
            ratio = float(limit_side_len) / max(height, width) if max(height, width) > limit_side_len else 1.0
        else:
            ratio = float(limit_side_len) / min(height, width) if min(height, width) < limit_side_len else 1.0
        resize_h = max(32, int(round(height * ratio / 32) * 32))
        resize_w = max(32, int(round(width * ratio / 32) * 32))
        return cv2.resize(image, (resize_w, resize_h))
