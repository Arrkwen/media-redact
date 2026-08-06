from pathlib import Path

import pytest

from media_redact.model.assets import _face_asset, ensure_model


def test_ensure_model_returns_existing(tmp_path, monkeypatch):
    target = tmp_path / "face_det.onnx"
    target.write_bytes(b"onnx")
    asset = _face_asset().__class__(
        path=target,
        url="http://example.invalid/model.onnx",
        label="test model",
    )

    def fail_download(*_args, **_kwargs):
        raise AssertionError("should not download")

    monkeypatch.setattr("media_redact.model.assets.urllib.request.urlretrieve", fail_download)
    assert ensure_model(asset) == target


def test_ensure_model_raises_for_custom_missing_path(tmp_path, monkeypatch):
    target = tmp_path / "missing.onnx"
    asset = _face_asset().__class__(
        path=target,
        url="http://example.invalid/model.onnx",
        label="test model",
    )

    with pytest.raises(FileNotFoundError, match="test model not found"):
        ensure_model(asset)


def test_ensure_model_downloads_to_managed_dir(monkeypatch, tmp_path):
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    target = model_dir / "face_det.onnx"
    asset = _face_asset().__class__(
        path=target,
        url="http://example.invalid/model.onnx",
        label="test model",
    )

    monkeypatch.setattr("media_redact.paths.get_model_dir", lambda: model_dir)

    def fake_download(url, dest):
        Path(dest).write_bytes(b"downloaded")

    monkeypatch.setattr("media_redact.model.assets.urllib.request.urlretrieve", fake_download)
    assert ensure_model(asset) == target
    assert target.read_bytes() == b"downloaded"
