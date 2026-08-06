"""ONNX Runtime 会话加载。"""

from __future__ import annotations

from pathlib import Path


def load_onnx_session(path: Path, *, model_label: str):
    import onnxruntime as ort

    providers = ort.get_available_providers()
    try:
        return ort.InferenceSession(str(path), providers=providers)
    except Exception as exc:
        message = str(exc)
        if "Unsupported model IR version" in message:
            raise RuntimeError(
                f"Failed to load {model_label} model {path}. "
                "PP-OCRv6 ONNX models require onnxruntime>=1.18. "
                f"Original error: {exc}"
            ) from exc
        raise
