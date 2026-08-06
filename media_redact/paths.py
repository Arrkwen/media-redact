"""项目资源路径常量与解析工具。"""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent

MODELS_DIR = PACKAGE_ROOT / "models"
DEFAULT_FACE_MODEL = MODELS_DIR / "face_det.onnx"
DEFAULT_TEXT_DET_MODEL = MODELS_DIR / "text_det.onnx"
DEFAULT_TEXT_REC_MODEL = MODELS_DIR / "text_rec.onnx"
DEFAULT_TEXT_DICT = MODELS_DIR / "ppocrv5_dict.txt"

DATA_DIR = PROJECT_ROOT / "assets" / "data"


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
