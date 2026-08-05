"""Tests for Python redaction API."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from media_redact.api import (
    _collect_files,
    _common_root,
    _resolve_output_path,
    redact_image,
)


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
        output=None,
        output_dir=output_dir,
        single_input=False,
    )
    assert output == (output_dir / "sub" / "clip_redacted.jpg").resolve()


def test_redact_image_directory_requires_output_dir(tmp_path):
    _write_image(tmp_path / "in" / "clip.jpg")

    with pytest.raises(ValueError, match="output_dir is required"):
        redact_image(tmp_path / "in", face=True)


def test_redact_image_batch_preserves_tree(tmp_path, monkeypatch):
    input_a = tmp_path / "in" / "a" / "one.jpg"
    input_b = tmp_path / "in" / "b" / "two.jpg"
    _write_image(input_a)
    _write_image(input_b)
    output_dir = tmp_path / "out"

    def fake_process_image(input_path, output_path, processor):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"ok")

    monkeypatch.setattr("media_redact.api.process_image", fake_process_image)
    monkeypatch.setattr(
        "media_redact.api.create_processor",
        lambda **kwargs: object(),
    )

    results = redact_image(
        tmp_path / "in",
        output_dir=output_dir,
        recursive=True,
        face=True,
    )
    assert results == sorted([
        (output_dir / "a" / "one_redacted.jpg").resolve(),
        (output_dir / "b" / "two_redacted.jpg").resolve(),
    ])
    assert all(path.exists() for path in results)


def test_redact_image_multiple_files(tmp_path, monkeypatch):
    input_a = tmp_path / "batch" / "a.jpg"
    input_b = tmp_path / "batch" / "b.jpg"
    _write_image(input_a)
    _write_image(input_b)
    output_dir = tmp_path / "out"

    def fake_process_image(input_path, output_path, processor):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"ok")

    monkeypatch.setattr("media_redact.api.process_image", fake_process_image)
    monkeypatch.setattr(
        "media_redact.api.create_processor",
        lambda **kwargs: object(),
    )

    results = redact_image(
        [input_a, input_b],
        output_dir=output_dir,
        osd=True,
        osd_regions=["0,0,1,1"],
    )
    assert results == [
        (output_dir / "a_redacted.jpg").resolve(),
        (output_dir / "b_redacted.jpg").resolve(),
    ]
