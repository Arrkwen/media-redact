"""OSD 区域坐标格式化（与 media-redact --osd-region / --osd-band 一致）。"""

from __future__ import annotations


def format_rect_region(x1: int, y1: int, x2: int, y2: int) -> str:
    """
    将 inclusive 角点转为 --osd-region 矩形格式。

    x2、y2 为 exclusive 边界，与 MaskRegion.from_bbox 一致。
    """
    left, right = sorted((x1, x2))
    top, bottom = sorted((y1, y2))
    return f"{left},{top},{right + 1},{bottom + 1}"


def format_polygon_region(points: list[tuple[int, int]]) -> str:
    """将顶点列表转为 --osd-region 多边形格式。"""
    if len(points) < 3:
        raise ValueError("Polygon requires at least 3 points")
    return ";".join(f"{x},{y}" for x, y in points)


def parse_region_specs(text: str) -> list[str]:
    """按行解析区域规格。"""
    return [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]


def _format_ratio(value: float) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text or "0"


def band_spec_from_line(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    *,
    image_width: int,
    image_height: int,
) -> str:
    """
    根据标注线段推断 ``--osd-band`` 规格。

    水平线：靠近顶部 → ``top:y/H``；靠近底部 → ``bottom:(H-y)/H``。
    垂直线：靠近左侧 → ``left:x/W``；靠近右侧 → ``right:(W-x)/W``。
    """
    if image_width <= 0 or image_height <= 0:
        raise ValueError("Image size must be positive.")

    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    if dx == 0 and dy == 0:
        raise ValueError("Band line requires two distinct points.")

    if dx >= dy:
        pos = round((y1 + y2) / 2)
        if pos <= image_height / 2:
            name = "top"
            ratio = pos / image_height
        else:
            name = "bottom"
            ratio = (image_height - pos) / image_height
    else:
        pos = round((x1 + x2) / 2)
        if pos <= image_width / 2:
            name = "left"
            ratio = pos / image_width
        else:
            name = "right"
            ratio = (image_width - pos) / image_width

    if not 0 < ratio < 1:
        raise ValueError(f"Band ratio must be between 0 and 1, got {ratio:.4f}.")
    return f"{name}:{_format_ratio(ratio)}"
