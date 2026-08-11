"""ONNX Runtime 设备选择与 InferenceSession 创建。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from media_redact.log import logger

if TYPE_CHECKING:
    import onnxruntime as ort

DeviceKind = Literal["auto", "cpu", "cuda"]
DEVICE_ENV = "MEDIA_REDACT_DEVICE"
DEFAULT_DEVICE: DeviceKind = "auto"


def normalize_device(device: str | None) -> DeviceKind:
    if device is None:
        device = os.environ.get(DEVICE_ENV, DEFAULT_DEVICE)
    normalized = device.strip().lower()
    if normalized not in ("auto", "cpu", "cuda"):
        raise ValueError(f"device must be one of auto, cpu, cuda; got {device!r}")
    return normalized  # type: ignore[return-value]


def resolve_providers(device: DeviceKind = DEFAULT_DEVICE) -> list[str]:
    import onnxruntime as ort

    available = ort.get_available_providers()
    if device == "cpu":
        return ["CPUExecutionProvider"]

    if device == "cuda":
        if "CUDAExecutionProvider" not in available:
            raise RuntimeError(
                "CUDAExecutionProvider is not available. "
                "Install onnxruntime-gpu (or a CUDA-enabled build) and ensure "
                "NVIDIA drivers are present."
            )
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]

    if "CUDAExecutionProvider" in available:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


def create_inference_session(
    path: str | Path,
    *,
    model_label: str,
    device: DeviceKind | str = DEFAULT_DEVICE,
) -> ort.InferenceSession:
    import onnxruntime as ort

    device_kind = normalize_device(device if isinstance(device, str) else device)
    providers = resolve_providers(device_kind)
    model_path = Path(path)
    try:
        session = ort.InferenceSession(str(model_path), providers=providers)
    except Exception as exc:
        message = str(exc)
        if "Unsupported model IR version" in message:
            raise RuntimeError(
                f"Failed to load {model_label} model {model_path}. "
                "PP-OCRv6 ONNX models require onnxruntime>=1.18. "
                f"Original error: {exc}"
            ) from exc
        raise

    active = session.get_providers()
    logger.info(
        "Loaded {} model with ONNX Runtime provider(s): {}",
        model_label,
        ", ".join(active),
    )
    if device_kind == "cuda" and active and active[0] != "CUDAExecutionProvider":
        logger.warning(
            "device=cuda requested but session fell back to {}; check CUDA setup",
            active[0],
        )
    return session
