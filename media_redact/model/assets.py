"""模型资源定义与按需下载。"""

from __future__ import annotations

import hashlib
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from media_redact import paths as path_utils
from media_redact.log import logger
from media_redact.paths import (
    TextModelSize,
    default_face_model,
    default_text_det_model,
    default_text_dict,
    default_text_rec_model,
)

_GITHUB_RAW_BASE = (
    "https://github.com/Arrkwen/media-redact/raw/master/assets/models"
)
_RAPIDOCR_BASE = "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.1"

# face_det.onnx is ~8.7 MB in repo
_MIN_ONNX_BYTES = 1024 * 1024
_MIN_DICT_BYTES = 1024

# SHA256 of RapidOCR v3.9.1 PP-OCRv6 ONNX files (verified at build time).
_TEXT_DET_SHA256: dict[TextModelSize, str] = {
    "tiny": "f42c0fbd294d95eac1a550e131b277dac97462c8025fa4b6c3cec1b7894bd3d5",
    "small": "090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f",
    "medium": "92078b7355007ccfffcd4c8cd441a3afd4538904d06881b29a155e1e679907c2",
}
_TEXT_REC_SHA256: dict[TextModelSize, str] = {
    "tiny": "e16e242de5937ad92609223f19bc2aff3727ee40b095f996907c24749bad251b",
    "small": "6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884",
    "medium": "eef444829dbbe18d7fea59a3f6eb75647518d2b3a9568d27c92e42940204894b",
}


@dataclass(frozen=True)
class ModelAsset:
    path: Path
    url: str
    label: str
    min_bytes: int = _MIN_ONNX_BYTES
    expected_sha256: str | None = None


def _face_asset() -> ModelAsset:
    return ModelAsset(
        default_face_model(),
        f"{_GITHUB_RAW_BASE}/face_det.onnx",
        "face detection model",
    )


def _text_det_asset(size: TextModelSize = "small") -> ModelAsset:
    return ModelAsset(
        default_text_det_model(size),
        f"{_RAPIDOCR_BASE}/onnx/PP-OCRv6/det/PP-OCRv6_det_{size}.onnx",
        f"text detection model ({size})",
        expected_sha256=_TEXT_DET_SHA256[size],
    )


def _text_rec_asset(size: TextModelSize = "small") -> ModelAsset:
    return ModelAsset(
        default_text_rec_model(size),
        f"{_RAPIDOCR_BASE}/onnx/PP-OCRv6/rec/PP-OCRv6_rec_{size}.onnx",
        f"text recognition model ({size})",
        expected_sha256=_TEXT_REC_SHA256[size],
    )


def _text_dict_asset() -> ModelAsset:
    return ModelAsset(
        default_text_dict(),
        f"{_RAPIDOCR_BASE}/paddle/PP-OCRv6/rec/PP-OCRv6_rec_small/ppocrv6_dict.txt",
        "OCR dictionary",
        min_bytes=_MIN_DICT_BYTES,
    )


def _is_managed_path(path: Path) -> bool:
    try:
        path.resolve().relative_to(path_utils.get_model_dir().resolve())
        return True
    except ValueError:
        return False


def _looks_like_html(path: Path) -> bool:
    with path.open("rb") as handle:
        head = handle.read(256).lstrip().lower()
    return head.startswith(b"<!doctype") or head.startswith(b"<html") or b"<html" in head


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_valid_cached_file(path: Path, asset: ModelAsset) -> bool:
    if not path.exists():
        return False
    size = path.stat().st_size
    if size < asset.min_bytes:
        return False
    if path.suffix == ".onnx" and _looks_like_html(path):
        return False
    if asset.expected_sha256 and _file_sha256(path) != asset.expected_sha256:
        return False
    return True


def _download_to(path: Path, url: str) -> None:
    request = urllib.request.Request(
        url, headers={"User-Agent": "media-redact/0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        if response.status and response.status >= 400:
            raise urllib.error.HTTPError(
                url, response.status, response.reason, response.headers, None
            )
        data = response.read()
    if len(data) < 64:
        raise RuntimeError(
            f"Download from {url} returned empty or truncated payload")
    if data.lstrip().lower().startswith(b"<!doctype") or data.lstrip().lower().startswith(b"<html"):
        raise RuntimeError(
            f"Download from {url} returned HTML instead of a model file; check the URL"
        )
    path.write_bytes(data)


def ensure_model(asset: ModelAsset) -> Path:
    """若本地缓存有效则返回路径；否则下载并在校验通过后返回。"""
    path = asset.path
    if _is_valid_cached_file(path, asset):
        return path

    if path.exists():
        reason = "invalid"
        if asset.expected_sha256:
            reason = "hash mismatch or invalid"
        logger.warning("Removing {} cached {} at {}", reason, asset.label, path)
        path.unlink()

    if not _is_managed_path(path):
        raise FileNotFoundError(f"{asset.label} not found: {path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading {} from {}", asset.label, asset.url)
    logger.info("Saving to {}", path)
    try:
        _download_to(path, asset.url)
    except (urllib.error.URLError, RuntimeError) as exc:
        if path.exists():
            path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Failed to download {asset.label} from {asset.url}: {exc}") from exc

    if not _is_valid_cached_file(path, asset):
        path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Downloaded {asset.label} failed validation (corrupt or too small): {path}"
        )

    size_mb = path.stat().st_size / 1024 / 1024
    logger.info("Downloaded {} ({:.2f} MB)", path.name, size_mb)
    return path


def ensure_face_model() -> Path:
    return ensure_model(_face_asset())


def ensure_text_det_model(size: TextModelSize = "small") -> Path:
    return ensure_model(_text_det_asset(size))


def ensure_text_rec_model(size: TextModelSize = "small") -> Path:
    return ensure_model(_text_rec_asset(size))


def ensure_text_dict() -> Path:
    return ensure_model(_text_dict_asset())


def ensure_ocr_models(
    *,
    require_rec: bool = False,
    model_size: TextModelSize = "small",
) -> None:
    """确保文字检测模型就绪；``require_rec`` 时同时拉取识别模型与字典。"""
    ensure_text_det_model(model_size)
    if require_rec:
        ensure_text_rec_model(model_size)
        ensure_text_dict()
