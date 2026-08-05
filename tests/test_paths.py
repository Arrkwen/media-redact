from media_redact.paths import (
    DATA_DIR,
    DEFAULT_FACE_MODEL,
    MODELS_DIR,
    PACKAGE_ROOT,
    default_output_path,
    resolve_path,
)


def test_asset_directories():
    assert MODELS_DIR == PACKAGE_ROOT / "models"
    assert DATA_DIR.name == "data"
    assert DEFAULT_FACE_MODEL == MODELS_DIR / "face_det.onnx"


def test_resolve_path_relative():
    resolved = resolve_path("assets/data")
    assert resolved.is_absolute()
    assert resolved.name == "data"


def test_default_output_path_in_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    input_file = tmp_path / "nested" / "clip.mp4"
    input_file.parent.mkdir(parents=True)
    input_file.touch()

    output = default_output_path(input_file.resolve())
    assert output.parent == tmp_path.resolve()
    assert output.name == "clip_redacted.mp4"
