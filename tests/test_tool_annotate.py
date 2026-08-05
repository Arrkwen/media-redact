"""Tests for annotate tool helpers."""

from pathlib import Path

import cv2
import numpy as np

import pytest

from media_redact.tool.annotate_region import DEFAULT_PORT, _error_stage, _safe_url, build_init_payload, extract_video_frame


def test_default_port():
    assert DEFAULT_PORT == 8765


def test_build_init_payload_no_media():
    assert build_init_payload(None) == {"media": None}


def test_build_init_payload_image(tmp_path):
    img_path = tmp_path / "sample.png"
    cv2.imwrite(str(img_path), np.zeros((108, 192, 3), dtype=np.uint8))
    payload = build_init_payload(img_path)
    assert payload["media"]["type"] == "image"
    assert payload["media"]["name"] == "sample.png"
    assert payload["media"]["url"] == "/api/file"
    assert payload["media"]["width"] == 192
    assert payload["media"]["height"] == 108


def test_template_supports_upload_and_stream():
    template = (
        Path(__file__).resolve().parents[1]
        / "media_redact/tool/templates/annotate.html"
    ).read_text(encoding="utf-8")
    assert "btn-upload-image" in template
    assert "btn-upload-video" in template
    assert "/api/init" in template
    assert "/api/extract-frame" in template
    assert "/api/stream/frame" in template


def test_error_stage():
    assert _error_stage("Stream connect failed: timeout") == "connect"
    assert _error_stage("Stream decode failed: invalid data") == "decode"


def test_safe_url_redacts_password():
    assert _safe_url("rtsp://admin:secret@192.168.1.1/stream") == "rtsp://admin:***@192.168.1.1/stream"


def test_extract_rtsp_local_connect_error():
    with pytest.raises(ValueError, match="connect|timeout|failed"):
        extract_video_frame("rtsp://127.0.0.1:9/nonexistent", frame_index=0)


def test_extract_video_frame(tmp_path):
    path = tmp_path / "test.avi"
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"MJPG"),
        10,
        (64, 48),
    )
    writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    writer.release()

    body, width, height = extract_video_frame(path, frame_index=0)
    assert width == 64
    assert height == 48
    assert body.startswith(b"\xff\xd8")
