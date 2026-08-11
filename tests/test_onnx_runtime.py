"""Tests for ONNX Runtime device selection."""

import pytest
from media_redact.model.onnx_runtime import (
    normalize_device,
    resolve_providers,
)


def test_normalize_device_accepts_values():
    assert normalize_device("auto") == "auto"
    assert normalize_device("cpu") == "cpu"
    assert normalize_device("cuda") == "cuda"


def test_normalize_device_rejects_invalid():
    with pytest.raises(ValueError, match="device must be one of"):
        normalize_device("gpu")


def test_normalize_device_reads_env(monkeypatch):
    monkeypatch.setenv("MEDIA_REDACT_DEVICE", "cpu")
    assert normalize_device(None) == "cpu"


def test_resolve_providers_cpu():
    assert resolve_providers("cpu") == ["CPUExecutionProvider"]


def test_resolve_providers_cuda_requires_cuda_ep(monkeypatch):
    monkeypatch.setattr(
        "onnxruntime.get_available_providers",
        lambda: ["CPUExecutionProvider"],
    )
    with pytest.raises(RuntimeError, match="CUDAExecutionProvider is not available"):
        resolve_providers("cuda")


def test_resolve_providers_auto_prefers_cuda(monkeypatch):
    monkeypatch.setattr(
        "onnxruntime.get_available_providers",
        lambda: ["CUDAExecutionProvider", "CPUExecutionProvider"],
    )
    assert resolve_providers("auto") == [
        "CUDAExecutionProvider",
        "CPUExecutionProvider",
    ]


def test_create_inference_session_uses_cpu(monkeypatch, tmp_path):
    from media_redact.model.onnx_runtime import create_inference_session

    model_path = tmp_path / "model.onnx"
    model_path.write_bytes(b"fake")

    captured: dict = {}

    class FakeSession:
        def __init__(self, path, providers=None):
            captured["providers"] = providers

        def get_providers(self):
            return captured["providers"]

    monkeypatch.setattr(
        "onnxruntime.InferenceSession",
        FakeSession,
    )
    monkeypatch.setattr(
        "media_redact.model.onnx_runtime.logger.info",
        lambda *args, **kwargs: None,
    )

    create_inference_session(model_path, model_label="test", device="cpu")
    assert captured["providers"] == ["CPUExecutionProvider"]
