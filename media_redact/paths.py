"""项目资源路径常量与解析工具。"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent

MODEL_ROOT_ENV = "MEDIA_REDACT_MODEL_ROOT"
DEFAULT_MODEL_SUBDIR = Path(".media_redact") / "models"

DATA_DIR = PROJECT_ROOT / "assets" / "data"


def get_model_dir() -> Path:
    """返回模型缓存目录，默认 ``~/.media_redact/models/``。"""
    override = os.environ.get(MODEL_ROOT_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / DEFAULT_MODEL_SUBDIR).resolve()


def default_face_model() -> Path:
    return get_model_dir() / "face_det.onnx"


def default_text_det_model() -> Path:
    return get_model_dir() / "text_det.onnx"


def default_text_rec_model() -> Path:
    return get_model_dir() / "text_rec.onnx"


def default_text_dict() -> Path:
    return get_model_dir() / "ppocrv5_dict.txt"


def resolve_path(path: str | Path) -> Path:
    """将相对路径解析为基于项目根目录的绝对路径。"""
    p = Path(path)
    if p.is_absolute():
        return p
    return PROJECT_ROOT / p


def resolve_input_path(path: str | Path) -> Path:
    """
    解析输入路径（文件或目录）。

    查找顺序：绝对路径 → 当前工作目录 → assets/data/
    """
    p = Path(path)
    if p.is_absolute():
        if p.exists():
            return p.resolve()
        raise FileNotFoundError(f"Input not found: {p}")

    cwd_candidate = Path.cwd() / p
    if cwd_candidate.exists():
        return cwd_candidate.resolve()

    assets_candidate = DATA_DIR / p
    if assets_candidate.exists():
        return assets_candidate.resolve()

    raise FileNotFoundError(
        f"Input not found: {p} (searched: {cwd_candidate}, {assets_candidate})"
    )


def default_output_path(input_path: Path) -> Path:
    """默认输出到当前工作目录：{stem}_redacted{suffix}。"""
    filename = f"{input_path.stem}_redacted{input_path.suffix}"
    return Path.cwd() / filename
