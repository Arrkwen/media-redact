"""YOLO ONNX 人脸检测器。"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from media_redact.detect.base import MaskRegion
from media_redact.detect.face.onnx_utils import (
    parse_model_input_size,
    postprocess_detection_outputs,
    postprocess_multiscale_outputs,
    preprocess_bgr,
)

DEFAULT_NMS_IOU = 0.3


class FaceDetector:
    """使用 ONNX Runtime 进行人脸检测。"""

    def __init__(
        self,
        model_path: str | Path,
        *,
        score_threshold: float = 0.3,
        image_format: str = "rgb",
        providers: list[str] | None = None,
    ) -> None:
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"ONNX model not found: {path}")

        import onnxruntime as ort

        if providers is None:
            providers = ort.get_available_providers()

        self._session = ort.InferenceSession(str(path), providers=providers)
        self.score_threshold = score_threshold
        self.image_format = image_format

        self.input_width, self.input_height = parse_model_input_size(path, self._session)
        self.input_name = self._session.get_inputs()[0].name

    def detect(self, image: np.ndarray) -> list[MaskRegion]:
        """
        检测人脸。

        Args:
            image: BGR uint8 图像 (H, W, 3)
        """
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        elif image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

        model_input, ratio, dw, dh = preprocess_bgr(
            image,
            self.input_width,
            self.input_height,
            image_format=self.image_format,
        )
        outputs = self._session.run(None, {self.input_name: model_input})

        if len(outputs) == 1:
            raw = postprocess_detection_outputs(
                outputs, ratio, dw, dh, self.score_threshold, DEFAULT_NMS_IOU
            )
        else:
            raw = postprocess_multiscale_outputs(
                outputs, ratio, dw, dh, self.score_threshold, DEFAULT_NMS_IOU
            )

        return [
            MaskRegion.from_bbox(
                x1=item["bbox"][0],
                y1=item["bbox"][1],
                x2=item["bbox"][2],
                y2=item["bbox"][3],
                score=item["score"],
                label="face",
            )
            for item in raw
        ]

    def close(self) -> None:
        self._session = None  # type: ignore[assignment]
