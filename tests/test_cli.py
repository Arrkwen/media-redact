"""Tests for media-redact CLI."""

import sys

from media_redact.cli import parse_args


def test_parse_args_face_only(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["media-redact", "clip.mp4", "--face"])
    args = parse_args()
    assert args.face is True
    assert args.osd is False


def test_parse_args_osd_with_regions(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "media-redact",
            "clip.mp4",
            "--osd",
            "--osd-region",
            "0,0,100,100",
        ],
    )
    args = parse_args()
    assert args.osd is True
    assert args.osd_region == ["0,0,100,100"]


def test_parse_args_face_and_osd(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "media-redact",
            "clip.mp4",
            "--face",
            "--osd",
            "--osd-region",
            "0,0,1,1",
        ],
    )
    args = parse_args()
    assert args.face is True
    assert args.osd is True
