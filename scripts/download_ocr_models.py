#!/usr/bin/env python3
"""下载 PP-OCRv5 OCR 模型与字典到 media_redact/models/。"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

BASE_URL = "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2"
MODELS_DIR = Path(__file__).resolve().parents[1] / "media_redact" / "models"

ASSETS = {
    "text_det.onnx": f"{BASE_URL}/onnx/PP-OCRv5/det/ch_PP-OCRv5_det_mobile.onnx",
    "text_rec.onnx": f"{BASE_URL}/onnx/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile.onnx",
    "ppocrv5_dict.txt": (
        f"{BASE_URL}/paddle/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile/ppocrv5_dict.txt"
    ),
}


def download(url: str, target: Path) -> None:
    if target.exists() and target.stat().st_size > 0:
        print(f"Already exists: {target.name}")
        return
    print(f"Downloading {url}")
    print(f"         -> {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, target)
    print(f"Done {target.name} ({target.stat().st_size / 1024 / 1024:.2f} MB)")


def main() -> int:
    for filename, url in ASSETS.items():
        download(url, MODELS_DIR / filename)
    print("All OCR assets ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
