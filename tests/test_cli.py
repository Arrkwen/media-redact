"""Tests for media-redact CLI."""

import sys

from media_redact.cli import parse_args


def test_parse_args_face_only(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["media-redact", "clip.mp4", "--face"])
    args = parse_args()
    assert args.face is True


def test_parse_args_osd_band_only(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["media-redact", "clip.mp4", "--osd-band", "bottom:0.12"],
    )
    args = parse_args()
    assert args.osd_band == ["bottom:0.12"]


def test_parse_args_multiple_osd_bands_and_patterns(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "media-redact",
            "clip.mp4",
            "--osd-band",
            "top:0.15",
            "--osd-band",
            "bottom:0.12",
            "--osd-band",
            "left:0.08",
            "--osd-text",
            r"\d{4}-\d{2}-\d{2}",
            "--osd-text",
            r"\d+\s*km/h",
        ],
    )
    args = parse_args()
    assert args.osd_band == ["top:0.15", "bottom:0.12", "left:0.08"]
    assert args.osd_text == [r"\d{4}-\d{2}-\d{2}", r"\d+\s*km/h"]


def test_parse_args_osd_text_only(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "media-redact",
            "clip.mp4",
            "--osd-text",
            r"\d{4}-\d{2}-\d{2}",
        ],
    )
    args = parse_args()
    assert args.osd_text == [r"\d{4}-\d{2}-\d{2}"]


def test_parse_args_osd_region_only(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "media-redact",
            "clip.mp4",
            "--osd-region",
            "0,0,100,100",
        ],
    )
    args = parse_args()
    assert args.osd_region == ["0,0,100,100"]


def test_parse_args_face_and_osd_region(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "media-redact",
            "clip.mp4",
            "--face",
            "--osd-region",
            "0,0,1,1",
        ],
    )
    args = parse_args()
    assert args.face is True
    assert args.osd_region == ["0,0,1,1"]


def test_parse_args_directory_batch_options(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "media-redact",
            "photos/",
            "--face",
            "-o",
            "out/",
            "--recursive",
        ],
    )
    args = parse_args()
    assert args.input == "photos/"
    assert args.output == "out/"
    assert args.recursive is True
