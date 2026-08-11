from pathlib import Path

import pytest
from media_redact.model.assets import (
    _download_to,
    _face_asset,
    _is_valid_cached_file,
    ensure_model,
)


def _valid_onnx_payload(prefix: bytes = b"onnx") -> bytes:
    return prefix + (b"\0" * (_MIN_ONNX_BYTES - len(prefix)))


# mirror module constant for tests
from media_redact.model.assets import _MIN_ONNX_BYTES  # noqa: E402


def test_ensure_model_returns_valid_existing(tmp_path, monkeypatch):
    target = tmp_path / "face_det.onnx"
    target.write_bytes(_valid_onnx_payload())
    asset = _face_asset().__class__(
        path=target,
        url="http://example.invalid/model.onnx",
        label="test model",
    )

    def fail_download(*_args, **_kwargs):
        raise AssertionError("should not download")

    monkeypatch.setattr("media_redact.model.assets._download_to", fail_download)
    assert ensure_model(asset) == target


def test_ensure_model_rejects_html_cache_and_redownloads(tmp_path, monkeypatch):
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    target = model_dir / "face_det.onnx"
    target.write_text("<html>404</html>")
    asset = _face_asset().__class__(
        path=target,
        url="http://example.invalid/model.onnx",
        label="test model",
    )

    monkeypatch.setattr("media_redact.paths.get_model_dir", lambda: model_dir)

    def fake_download(path: Path, url: str) -> None:
        path.write_bytes(_valid_onnx_payload(b"fresh"))

    monkeypatch.setattr("media_redact.model.assets._download_to", fake_download)
    assert ensure_model(asset) == target
    assert target.read_bytes().startswith(b"fresh")


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

    def fake_download(path: Path, url: str) -> None:
        path.write_bytes(_valid_onnx_payload(b"downloaded"))

    monkeypatch.setattr("media_redact.model.assets._download_to", fake_download)
    assert ensure_model(asset) == target
    assert target.read_bytes().startswith(b"downloaded")


def test_is_valid_cached_file_rejects_html(tmp_path):
    path = tmp_path / "bad.onnx"
    path.write_text("<html>error</html>")
    asset = _face_asset().__class__(
        path=path,
        url="http://example.invalid/model.onnx",
        label="test model",
    )
    assert not _is_valid_cached_file(path, asset)


def test_is_valid_cached_file_rejects_hash_mismatch(tmp_path):
    path = tmp_path / "text_det_small.onnx"
    path.write_bytes(_valid_onnx_payload(b"wrong-model"))
    asset = _face_asset().__class__(
        path=path,
        url="http://example.invalid/model.onnx",
        label="text detection model (small)",
        expected_sha256="090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f",
    )
    assert not _is_valid_cached_file(path, asset)


def test_ensure_model_redownloads_on_hash_mismatch(tmp_path, monkeypatch):
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    target = model_dir / "text_det_small.onnx"
    target.write_bytes(_valid_onnx_payload(b"stale"))
    asset = _face_asset().__class__(
        path=target,
        url="http://example.invalid/model.onnx",
        label="text detection model (small)",
        expected_sha256="090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f",
    )

    monkeypatch.setattr("media_redact.paths.get_model_dir", lambda: model_dir)

    def fake_download(path: Path, url: str) -> None:
        path.write_bytes(_valid_onnx_payload(b"fresh"))

    monkeypatch.setattr("media_redact.model.assets._download_to", fake_download)
    monkeypatch.setattr(
        "media_redact.model.assets._is_valid_cached_file",
        lambda p, a: p.read_bytes().startswith(b"fresh"),
    )
    assert ensure_model(asset) == target
    assert target.read_bytes().startswith(b"fresh")


def test_download_to_rejects_html_response(tmp_path):
    class FakeResponse:
        status = 200

        def read(self):
            return b"<html>" + b"not found" * 16 + b"</html>"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(_request, timeout=120):
        return FakeResponse()

    monkeypatch_target = tmp_path / "out.onnx"
    import media_redact.model.assets as assets_module

    original = assets_module.urllib.request.urlopen
    assets_module.urllib.request.urlopen = fake_urlopen
    try:
        with pytest.raises(RuntimeError, match="HTML instead of a model file"):
            _download_to(monkeypatch_target, "http://example.invalid/model.onnx")
    finally:
        assets_module.urllib.request.urlopen = original
