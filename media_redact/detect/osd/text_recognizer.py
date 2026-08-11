"""PP-OCRv6 文字识别器。"""

from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

from media_redact.detect.osd.onnx_utils import load_onnx_session
from media_redact.detect.osd.text_rec_postprocess import CTCLabelDecode
from media_redact.model.onnx_runtime import DeviceKind


class TextRecognizer:
    """使用 PP-OCRv6_rec_small ONNX 识别文字。"""

    def __init__(
        self,
        model_path: str | Path,
        dict_path: str | Path,
        *,
        rec_image_shape: tuple[int, int, int] = (3, 48, 320),
        batch_size: int = 8,
        device: DeviceKind | str = "auto",
    ) -> None:
        path = Path(model_path)
        dictionary = Path(dict_path)
        if not path.exists():
            raise FileNotFoundError(f"Text recognition model not found: {path}")
        if not dictionary.exists():
            raise FileNotFoundError(f"Text recognition dictionary not found: {dictionary}")

        self._session = load_onnx_session(
            path,
            model_label="text recognition",
            device=device,
        )
        self.input_name = self._session.get_inputs()[0].name
        self.rec_image_shape = rec_image_shape
        self.batch_size = batch_size
        self.decoder = CTCLabelDecode(dictionary)

    def recognize(self, crops: list[np.ndarray | None]) -> list[tuple[str, float]]:
        if not crops:
            return []

        results: list[tuple[str, float]] = [("", 0.0)] * len(crops)
        indexed = [(index, crop) for index, crop in enumerate(crops) if crop is not None]
        if not indexed:
            return results

        for start in range(0, len(indexed), self.batch_size):
            batch = indexed[start : start + self.batch_size]
            batch_indices = [item[0] for item in batch]
            batch_crops = [item[1] for item in batch]
            batch_results = self._recognize_batch(batch_crops)
            for index, result in zip(batch_indices, batch_results, strict=True):
                results[index] = result
        return results

    def _recognize_batch(self, crops: list[np.ndarray]) -> list[tuple[str, float]]:
        _, img_height, img_width = self.rec_image_shape
        width_ratios = [crop.shape[1] / float(crop.shape[0]) for crop in crops]
        max_wh_ratio = max(img_width / img_height, max(width_ratios))

        batch_tensor = []
        for crop in crops:
            batch_tensor.append(self._resize_norm_img(crop, max_wh_ratio))
        model_input = np.concatenate(batch_tensor, axis=0).astype(np.float32)
        outputs = self._session.run(None, {self.input_name: model_input})
        return self.decoder.decode(outputs[0])

    def _resize_norm_img(self, image: np.ndarray, max_wh_ratio: float) -> np.ndarray:
        img_channel, img_height, img_width = self.rec_image_shape
        max_width = int(img_height * max_wh_ratio)
        height, width = image.shape[:2]
        ratio = width / float(height)
        resized_width = min(max_width, int(math.ceil(img_height * ratio)))
        resized = cv2.resize(image, (resized_width, img_height))
        resized = resized.astype(np.float32).transpose(2, 0, 1) / 255.0
        resized = (resized - 0.5) / 0.5

        padding = np.zeros((img_channel, img_height, max_width), dtype=np.float32)
        padding[:, :, :resized_width] = resized
        return np.expand_dims(padding, axis=0)
