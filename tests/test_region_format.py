"""Tests for region/band formatting helpers."""

import pytest
from media_redact.tool.region_format import band_spec_from_line, format_rect_region


def test_format_rect_region():
    assert format_rect_region(10, 20, 30, 40) == "10,20,31,41"


def test_band_spec_from_horizontal_top_line():
    assert band_spec_from_line(0, 162, 100, 162, image_width=1920, image_height=1080) == "top:0.15"


def test_band_spec_from_horizontal_bottom_line():
    assert (
        band_spec_from_line(0, 950, 100, 950, image_width=1920, image_height=1080) == "bottom:0.1204"
    )


def test_band_spec_from_vertical_left_line():
    assert band_spec_from_line(154, 0, 154, 100, image_width=1920, image_height=1080) == "left:0.0802"


def test_band_spec_from_vertical_right_line():
    assert (
        band_spec_from_line(1760, 0, 1760, 100, image_width=1920, image_height=1080) == "right:0.0833"
    )


def test_band_spec_rejects_degenerate_line():
    with pytest.raises(ValueError, match="distinct points"):
        band_spec_from_line(10, 10, 10, 10, image_width=100, image_height=100)
