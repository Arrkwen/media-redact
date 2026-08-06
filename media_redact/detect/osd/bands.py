"""OSD band 限域。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from media_redact.detect.base import MaskRegion

_VERTICAL_BANDS = frozenset({"top", "bottom"})
_HORIZONTAL_BANDS = frozenset({"left", "right"})
VALID_BAND_NAMES = _VERTICAL_BANDS | _HORIZONTAL_BANDS


@dataclass(frozen=True)
class BandSpec:
    name: str
    ratio: float


def parse_osd_band(spec: str) -> BandSpec:
    """
    解析 band 规格。

    格式: ``top:0.15``、``bottom:0.12``、``left:0.08``、``right:0.08``。
    上下 band 比例为相对整图高度，左右 band 为相对整图宽度。
    """
    body = spec.strip()
    if ":" not in body:
        raise ValueError(
            f"Invalid osd band spec: {spec!r}. "
            "Use top:0.15, bottom:0.12, left:0.08, or right:0.08."
        )
    name, ratio_text = body.split(":", 1)
    name = name.strip().lower()
    if name not in VALID_BAND_NAMES:
        raise ValueError(
            f"Unsupported band name {name!r}. Use top, bottom, left, or right."
        )
    ratio = float(ratio_text.strip())
    if not 0 < ratio < 1:
        raise ValueError(f"Band ratio must be between 0 and 1, got {ratio}.")
    return BandSpec(name=name, ratio=ratio)


def crop_band(image: np.ndarray, band: BandSpec) -> tuple[np.ndarray, int, int]:
    """裁剪 band 并返回 (crop, offset_x, offset_y)。"""
    height, width = image.shape[:2]
    if band.name == "top":
        band_height = max(1, int(round(height * band.ratio)))
        return image[0:band_height], 0, 0
    if band.name == "bottom":
        band_height = max(1, int(round(height * band.ratio)))
        offset_y = height - band_height
        return image[offset_y:height], 0, offset_y
    if band.name == "left":
        band_width = max(1, int(round(width * band.ratio)))
        return image[:, 0:band_width], 0, 0
    band_width = max(1, int(round(width * band.ratio)))
    offset_x = width - band_width
    return image[:, offset_x:width], offset_x, 0


def default_bands() -> list[BandSpec]:
    """行车记录仪/监控常见上下 OSD 区域。"""
    return [BandSpec("top", 0.15), BandSpec("bottom", 0.12)]


def band_y_range(image_height: int, band: BandSpec) -> tuple[int, int]:
    """返回上下 band 在整图中的 y 范围 ``[y_min, y_max)``（像素）。"""
    if band.name not in _VERTICAL_BANDS:
        raise ValueError(f"band_y_range expects a vertical band, got {band.name!r}.")
    band_height = max(1, int(round(image_height * band.ratio)))
    if band.name == "top":
        return 0, band_height
    return image_height - band_height, image_height


def band_x_range(image_width: int, band: BandSpec) -> tuple[int, int]:
    """返回左右 band 在整图中的 x 范围 ``[x_min, x_max)``（像素）。"""
    if band.name not in _HORIZONTAL_BANDS:
        raise ValueError(f"band_x_range expects a horizontal band, got {band.name!r}.")
    band_width = max(1, int(round(image_width * band.ratio)))
    if band.name == "left":
        return 0, band_width
    return image_width - band_width, image_width


def region_in_band(
    region: MaskRegion,
    image_width: int,
    image_height: int,
    band: BandSpec,
) -> bool:
    """bbox 中心点落在 band 范围内则视为在 band 内。"""
    x1, y1, x2, y2 = region.bounding_box()
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2
    if band.name in _VERTICAL_BANDS:
        y_min, y_max = band_y_range(image_height, band)
        return y_min <= center_y < y_max
    x_min, x_max = band_x_range(image_width, band)
    return x_min <= center_x < x_max


def filter_regions_by_bands(
    regions: list[MaskRegion],
    image_width: int,
    image_height: int,
    bands: list[BandSpec] | None,
) -> list[MaskRegion]:
    """保留中心点落在任一 band 内的检测框。"""
    if not bands:
        return regions
    return [
        region
        for region in regions
        if any(region_in_band(region, image_width, image_height, band) for band in bands)
    ]
