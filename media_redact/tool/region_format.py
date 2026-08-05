"""OSD 区域坐标格式化（与 media-redact --osd-region 一致）。"""

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
