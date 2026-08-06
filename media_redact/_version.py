"""从 pyproject.toml（或已安装包元数据）解析版本号。"""

from __future__ import annotations

import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

_PACKAGE_NAME = "media-redact"
_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _version_from_pyproject() -> str:
    text = _PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise RuntimeError(f"version not found in {_PYPROJECT}")
    return match.group(1)


def get_version() -> str:
    try:
        return version(_PACKAGE_NAME)
    except PackageNotFoundError:
        return _version_from_pyproject()


__version__ = get_version()
