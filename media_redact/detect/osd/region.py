"""固定区域 OSD 检测器。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from media_redact.detect.base import MaskRegion
from media_redact.log import logger


@dataclass
class OSDRegion:
    name: str
    rect: tuple[int, int, int, int] | None = None
    polygon: list[tuple[int, int]] | None = None


@dataclass
class OSDConfig:
    regions: list[OSDRegion]


def parse_osd_region(spec: str, index: int = 0) -> OSDRegion:
    """
    解析 CLI ``--osd-region`` 参数（绝对像素坐标）。

    格式:
      - 矩形: ``x1,y1,x2,y2``
      - 多边形: ``x1,y1;x2,y2;...``（>= 3 个点，用 ``;`` 分隔）
    """
    body = spec.strip()
    if not body:
        raise ValueError("OSD region spec cannot be empty")

    name = f"region_{index}"

    if ";" in body:
        polygon = _parse_polygon_pairs(body.split(";"))
        return OSDRegion(name=name, polygon=polygon)

    values = [int(part.strip()) for part in body.split(",") if part.strip()]
    if len(values) == 4:
        return OSDRegion(name=name, rect=(values[0], values[1], values[2], values[3]))

    raise ValueError(
        "Invalid --osd-region format. Use x1,y1,x2,y2 for rect (pixels), "
        "or x1,y1;x2,y2;... for polygon (pixels)."
    )


def _parse_polygon_pairs(parts: list[str]) -> list[tuple[int, int]]:
    polygon: list[tuple[int, int]] = []
    for part in parts:
        chunk = part.strip()
        if not chunk:
            continue
        xy = [int(value.strip()) for value in chunk.split(",")]
        if len(xy) != 2:
            raise ValueError(f"Invalid polygon point: {part}")
        polygon.append((xy[0], xy[1]))
    if len(polygon) < 3:
        raise ValueError("Polygon region requires at least 3 points")
    return polygon


def _region_fully_inside(region: OSDRegion, width: int, height: int) -> bool:
    """区域是否完全落在图像范围内。"""
    if region.polygon is not None:
        mask_region = MaskRegion.from_polygon(region.polygon, label=region.name)
    else:
        mask_region = MaskRegion.from_rect(region.rect, label=region.name)  # type: ignore[arg-type]
    return mask_region.fully_inside(width, height)


class RegionOSDDetector:
    """根据区域定义生成 OSD 打码区域。"""

    def __init__(self, config: OSDConfig) -> None:
        self.config = config

    @classmethod
    def from_regions(cls, regions: list[OSDRegion]) -> RegionOSDDetector:
        return cls(OSDConfig(regions=regions))

    @classmethod
    def from_specs(cls, specs: list[str]) -> RegionOSDDetector:
        regions = [parse_osd_region(spec, index=i) for i, spec in enumerate(specs)]
        return cls.from_regions(regions)

    def detect(self, image: np.ndarray) -> list[MaskRegion]:
        h, w = image.shape[:2]
        regions: list[MaskRegion] = []
        for region in self.config.regions:
            if not _region_fully_inside(region, w, h):
                logger.debug(
                    "Skip OSD region {}: outside image bounds {}x{}",
                    region.name,
                    w,
                    h,
                )
                continue
            if region.polygon is not None:
                mask_region = MaskRegion.from_polygon(
                    region.polygon,
                    label=region.name,
                )
            else:
                mask_region = MaskRegion.from_rect(
                    region.rect,  # type: ignore[arg-type]
                    label=region.name,
                )
            regions.append(mask_region)
        return regions
