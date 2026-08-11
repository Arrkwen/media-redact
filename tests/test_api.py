"""Tests for Python redaction API."""

from pathlib import Path

import cv2
import numpy as np
from media_redact.api import (
    _collect_files,
    _common_root,
    _resolve_output_path,
    redact_image,
)
from media_redact.paths import default_output_dir, resolve_output_dir


def _write_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), np.zeros((8, 8, 3), dtype=np.uint8))


def test_common_root_for_nested_files(tmp_path):
    a = tmp_path / "data" / "a" / "one.jpg"
    b = tmp_path / "data" / "b" / "two.jpg"
    _write_image(a)
    _write_image(b)

    root = _common_root([a.parent, b.parent])
    assert root == (tmp_path / "data").resolve()


def test_collect_files_from_directory_recursive(tmp_path):
    top = tmp_path / "in" / "clip.jpg"
    nested = tmp_path / "in" / "sub" / "nested.jpg"
    _write_image(top)
    _write_image(nested)

    files, root, has_directory_input = _collect_files(
        tmp_path / "in",
        "image",
        recursive=True,
    )
    assert has_directory_input is True
    assert root == (tmp_path / "in").resolve()
    assert files == sorted([top.resolve(), nested.resolve()])


def test_collect_files_non_recursive_skips_subdir(tmp_path):
    top = tmp_path / "in" / "clip.jpg"
    nested = tmp_path / "in" / "sub" / "nested.jpg"
    _write_image(top)
    _write_image(nested)

    files, root, has_directory_input = _collect_files(
        tmp_path / "in",
        "image",
        recursive=False,
    )
    assert has_directory_input is True
    assert files == [top.resolve()]


def test_resolve_output_path_preserves_subdirs(tmp_path):
    input_file = tmp_path / "in" / "sub" / "clip.jpg"
    input_root = tmp_path / "in"
    output_dir = tmp_path / "out"

    output = _resolve_output_path(
        input_file.resolve(),
        input_root.resolve(),
        output_dir.resolve(),
    )
    assert output == (output_dir / "sub" / "clip.jpg").resolve()


def test_resolve_output_path_single_file(tmp_path):
    input_file = tmp_path / "photos" / "clip.jpg"
    output_dir = tmp_path / "output_redact"

    output = _resolve_output_path(
        input_file.resolve(),
        input_file.parent.resolve(),
        output_dir.resolve(),
    )
    assert output == (output_dir / "clip.jpg").resolve()


def test_default_output_dir_in_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert default_output_dir() == (tmp_path / "output_redact").resolve()
    assert resolve_output_dir(None) == (tmp_path / "output_redact").resolve()
    assert resolve_output_dir("custom") == (tmp_path / "custom").resolve()


def test_redact_image_directory_uses_default_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_image(tmp_path / "in" / "clip.jpg")

    def fake_process_images(pairs, processor, **kwargs):
        for _input_path, output_path in pairs:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"ok")

    monkeypatch.setattr("media_redact.api.process_images", fake_process_images)
    monkeypatch.setattr(
        "media_redact.api.create_processor",
        lambda **kwargs: object(),
    )

    results = redact_image(tmp_path / "in", face=True)
    assert results == [(tmp_path / "output_redact" / "clip.jpg").resolve()]
    assert results[0].exists()


def test_redact_image_batch_preserves_tree(tmp_path, monkeypatch):
    input_a = tmp_path / "in" / "a" / "one.jpg"
    input_b = tmp_path / "in" / "b" / "two.jpg"
    _write_image(input_a)
    _write_image(input_b)
    output_dir = tmp_path / "out"

    def fake_process_images(pairs, processor, **kwargs):
        for _input_path, output_path in pairs:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"ok")

    monkeypatch.setattr("media_redact.api.process_images", fake_process_images)
    monkeypatch.setattr(
        "media_redact.api.create_processor",
        lambda **kwargs: object(),
    )

    results = redact_image(
        tmp_path / "in",
        output=output_dir,
        recursive=True,
        face=True,
    )
    assert results == sorted(
        [
            (output_dir / "a" / "one.jpg").resolve(),
            (output_dir / "b" / "two.jpg").resolve(),
        ]
    )
    assert all(path.exists() for path in results)


def test_redact_image_multiple_files(tmp_path, monkeypatch):
    input_a = tmp_path / "batch" / "a.jpg"
    input_b = tmp_path / "batch" / "b.jpg"
    _write_image(input_a)
    _write_image(input_b)
    output_dir = tmp_path / "out"

    def fake_process_images(pairs, processor, **kwargs):
        for _input_path, output_path in pairs:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"ok")

    monkeypatch.setattr("media_redact.api.process_images", fake_process_images)
    monkeypatch.setattr(
        "media_redact.api.create_processor",
        lambda **kwargs: object(),
    )

    results = redact_image(
        [input_a, input_b],
        output=output_dir,
        osd_regions=["0,0,1,1"],
    )
    assert results == [
        (output_dir / "a.jpg").resolve(),
        (output_dir / "b.jpg").resolve(),
    ]


def test_redact_image_passes_num_worker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_image(tmp_path / "photo.jpg")
    captured: dict = {}

    def fake_process_images(pairs, processor, **kwargs):
        captured.update(kwargs)
        for _input_path, output_path in pairs:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"ok")

    monkeypatch.setattr("media_redact.api.process_images", fake_process_images)
    monkeypatch.setattr(
        "media_redact.api.create_processor",
        lambda **kwargs: object(),
    )

    redact_image(tmp_path / "photo.jpg", face=True, num_worker=8)
    assert captured["num_worker"] == 8
