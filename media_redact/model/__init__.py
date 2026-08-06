"""按需下载 ONNX 模型与字典到用户模型缓存目录。"""

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
