#!/usr/bin/env python3
"""下载 PP-OCRv5 mobile det ONNX 到 media_redact/models/text_det.onnx。"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

MODEL_URL = (
    "https://www.modelscope.cn/models/RapidAI/RapidOCR/"
    "resolve/v3.9.2/onnx/PP-OCRv5/det/ch_PP-OCRv5_det_mobile.onnx"
)
TARGET = Path(__file__).resolve().parents[1] / "media_redact" / "models" / "text_det.onnx"

# PP-OCRv5_mobile_det (RapidOCR ONNX). Requires onnxruntime>=1.18 (ONNX IR v10).
# On older Linux (e.g. CentOS 7, max onnxruntime 1.16), use a newer host or wait for
# a compatible wheel before enabling --osd-text.


def main() -> int:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if TARGET.exists() and TARGET.stat().st_size > 0:
        print(f"Already exists: {TARGET}")
        return 0
    print(f"Downloading {MODEL_URL}")
    print(f"         -> {TARGET}")
    urllib.request.urlretrieve(MODEL_URL, TARGET)
    print(f"Done ({TARGET.stat().st_size / 1024 / 1024:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
