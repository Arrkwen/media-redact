"""CLI integration tests."""

import sys
from pathlib import Path

from media_redact.cli import main


def test_cli_directory_batch_calls_api(tmp_path, monkeypatch):
    input_dir = tmp_path / "photos"
    nested = input_dir / "a"
    nested.mkdir(parents=True)
    (nested / "one.jpg").write_bytes(b"fake")
    (input_dir / "clip.mp4").write_bytes(b"fake")

    calls: list[tuple[str, dict]] = []

    def fake_redact_image(inputs, output=None, **kwargs):
        calls.append(("image", {"inputs": inputs, "output": output, **kwargs}))
        return [Path(output) / "a" / "one.jpg"]

    def fake_redact_video(inputs, output=None, **kwargs):
        calls.append(("video", {"inputs": inputs, "output": output, **kwargs}))
        return [Path(output) / "clip.mp4"]

    monkeypatch.setattr(sys, "argv", ["media-redact", str(input_dir), "--face", "-r"])
    monkeypatch.setattr("media_redact.cli.redact_image", fake_redact_image)
    monkeypatch.setattr("media_redact.cli.redact_video", fake_redact_video)

    main()

    assert len(calls) == 2
    assert calls[0][0] == "image"
    assert calls[1][0] == "video"
    assert calls[0][1]["recursive"] is True
    assert calls[0][1]["output"] == Path.cwd() / "output_redact"


def test_cli_directory_with_output(tmp_path, monkeypatch):
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    (input_dir / "a.jpg").write_bytes(b"fake")
    output_dir = tmp_path / "out"

    captured: dict = {}

    def fake_redact_image(inputs, output=None, **kwargs):
        captured.update({"output": output, **kwargs})
        return [output_dir / "a.jpg"]

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "media-redact",
            str(input_dir),
            "--face",
            "-o",
            str(output_dir),
        ],
    )
    monkeypatch.setattr("media_redact.cli.redact_image", fake_redact_image)
    monkeypatch.setattr(
        "media_redact.cli.redact_video",
        lambda inputs, output=None, **kwargs: (_ for _ in ()).throw(
            FileNotFoundError("No videos found in the given inputs.")
        ),
    )

    main()

    assert captured["output"] == output_dir.resolve()
