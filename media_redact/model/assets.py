"""模型资源定义与按需下载。"""

from __future__ import annotations

import urllib.request
from dataclasses import dataclass
from pathlib import Path

from media_redact.log import logger
from media_redact.paths import (
    DEFAULT_FACE_MODEL,
    DEFAULT_TEXT_DET_MODEL,
    DEFAULT_TEXT_DICT,
    DEFAULT_TEXT_REC_MODEL,
    MODEL_DIR,
)

_GITHUB_RAW_BASE = (
    "https://github.com/Arrkwen/media-redact/raw/main/media_redact/model"
)
_RAPIDOCR_BASE = "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2"


@dataclass(frozen=True)
class ModelAsset:
    path: Path
    url: str
    label: str


FACE_ASSET = ModelAsset(
    DEFAULT_FACE_MODEL,
    f"{_GITHUB_RAW_BASE}/face_det.onnx",
    "face detection model",
)
TEXT_DET_ASSET = ModelAsset(
    DEFAULT_TEXT_DET_MODEL,
    f"{_RAPIDOCR_BASE}/onnx/PP-OCRv5/det/ch_PP-OCRv5_det_mobile.onnx",
    "text detection model",
)
TEXT_REC_ASSET = ModelAsset(
    DEFAULT_TEXT_REC_MODEL,
    f"{_RAPIDOCR_BASE}/onnx/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile.onnx",
    "text recognition model",
)
TEXT_DICT_ASSET = ModelAsset(
    DEFAULT_TEXT_DICT,
    f"{_RAPIDOCR_BASE}/paddle/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile/ppocrv5_dict.txt",
    "OCR dictionary",
)


def _is_managed_path(path: Path) -> bool:
    try:
        path.resolve().relative_to(MODEL_DIR.resolve())
        return True
    except ValueError:
        return False


def ensure_model(asset: ModelAsset) -> Path:
    """若本地已有则返回路径；仅在默认 model 目录下缺失时自动下载。"""
    path = asset.path
    if path.exists() and path.stat().st_size > 0:
        return path

    if not _is_managed_path(path):
        raise FileNotFoundError(f"{asset.label} not found: {path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading {} from {}", asset.label, asset.url)
    logger.info("Saving to {}", path)
    urllib.request.urlretrieve(asset.url, path)
    size_mb = path.stat().st_size / 1024 / 1024
    logger.info("Downloaded {} ({:.2f} MB)", path.name, size_mb)
    return path


def ensure_face_model() -> Path:
    return ensure_model(FACE_ASSET)


def ensure_text_det_model() -> Path:
    return ensure_model(TEXT_DET_ASSET)


def ensure_text_rec_model() -> Path:
    return ensure_model(TEXT_REC_ASSET)


def ensure_text_dict() -> Path:
    return ensure_model(TEXT_DICT_ASSET)


def ensure_ocr_models(*, require_rec: bool = False) -> None:
    """确保文字检测模型就绪；``require_rec`` 时同时拉取识别模型与字典。"""
    ensure_text_det_model()
    if require_rec:
        ensure_text_rec_model()
        ensure_text_dict()
