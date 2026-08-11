"""ONNX Runtime 会话加载。"""

from __future__ import annotations

from pathlib import Path

from media_redact.model.onnx_runtime import DeviceKind, create_inference_session


def load_onnx_session(
    path: Path,
    *,
    model_label: str,
    device: DeviceKind | str = "auto",
):
    return create_inference_session(path, model_label=model_label, device=device)
