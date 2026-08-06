"""按需下载 ONNX 模型与字典到 ``media_redact/model/``。"""

from media_redact.model.assets import (
    ensure_face_model,
    ensure_ocr_models,
    ensure_text_det_model,
    ensure_text_dict,
    ensure_text_rec_model,
)

__all__ = [
    "ensure_face_model",
    "ensure_ocr_models",
    "ensure_text_det_model",
    "ensure_text_dict",
    "ensure_text_rec_model",
]
