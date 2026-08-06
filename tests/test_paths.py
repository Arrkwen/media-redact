from media_redact.paths import (
    DATA_DIR,
    MODEL_ROOT_ENV,
    default_face_model,
    default_text_det_model,
    default_text_dict,
    default_text_rec_model,
    get_model_dir,
)


def test_default_model_dir(monkeypatch, tmp_path):
    monkeypatch.delenv(MODEL_ROOT_ENV, raising=False)
    monkeypatch.setattr("media_redact.paths.Path.home", lambda: tmp_path)

    model_dir = get_model_dir()
    assert model_dir == (tmp_path / ".media_redact" / "models").resolve()
    assert default_face_model() == model_dir / "face_det.onnx"
    assert default_text_det_model() == model_dir / "text_det.onnx"
    assert default_text_rec_model() == model_dir / "text_rec.onnx"
    assert default_text_dict() == model_dir / "ppocrv5_dict.txt"


def test_model_dir_env_override(monkeypatch, tmp_path):
    custom = tmp_path / "custom_models"
    monkeypatch.setenv(MODEL_ROOT_ENV, str(custom))

    assert get_model_dir() == custom.resolve()
    assert default_face_model() == custom / "face_det.onnx"


def test_asset_directories():
    assert DATA_DIR.name == "data"


def test_resolve_path_relative():
    from media_redact.paths import resolve_path

    resolved = resolve_path("assets/data")
    assert resolved.is_absolute()
    assert resolved.name == "data"


def test_default_output_path_in_cwd(tmp_path, monkeypatch):
    from media_redact.paths import default_output_path

    monkeypatch.chdir(tmp_path)
    input_file = tmp_path / "nested" / "clip.mp4"
    input_file.parent.mkdir(parents=True)
    input_file.touch()

    output = default_output_path(input_file.resolve())
    assert output.parent == tmp_path.resolve()
    assert output.name == "clip_redacted.mp4"
