"""打码区域数据结构。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MaskRegion:
    """打码区域，使用多边形顶点表示（绝对像素坐标）。"""

    polygon: list[tuple[int, int]]
    score: float = 1.0
    label: str = "face"

    @classmethod
    def from_bbox(
        cls,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        *,
        score: float = 1.0,
        label: str = "face",
    ) -> MaskRegion:
        # x2/y2 为切片意义上的 exclusive 边界
        return cls(
            polygon=[
                (x1, y1),
                (x2 - 1, y1),
                (x2 - 1, y2 - 1),
                (x1, y2 - 1),
            ],
            score=score,
            label=label,
        )

    @classmethod
    def from_rect(
        cls,
        rect: tuple[int, int, int, int],
        *,
        label: str,
    ) -> MaskRegion:
        x1, y1, x2, y2 = rect
        return cls.from_bbox(x1, y1, x2, y2, label=label)

    @classmethod
    def from_polygon(
        cls,
        points: list[tuple[int, int]],
        *,
        label: str,
    ) -> MaskRegion:
        return cls(polygon=list(points), label=label)

    def bounding_box(self) -> tuple[int, int, int, int]:
        xs = [point[0] for point in self.polygon]
        ys = [point[1] for point in self.polygon]
        return min(xs), min(ys), max(xs) + 1, max(ys) + 1

    def fully_inside(self, width: int, height: int) -> bool:
        """bbox 是否完全落在图像范围内。"""
        x1, y1, x2, y2 = self.bounding_box()
        return x1 >= 0 and y1 >= 0 and x2 <= width and y2 <= height

    def max_uniform_scale(self, width: int, height: int) -> float:
        """围绕多边形中心均匀放大、且仍完全落在图像内的最大倍率。"""
        if width <= 0 or height <= 0 or len(self.polygon) < 3:
            return 1.0

        cx = sum(point[0] for point in self.polygon) / len(self.polygon)
        cy = sum(point[1] for point in self.polygon) / len(self.polygon)
        max_x = width - 1
        max_y = height - 1
        limits = [float("inf")]
        for x, y in self.polygon:
            if x > cx:
                limits.append((max_x - cx) / (x - cx))
            elif x < cx:
                limits.append(cx / (cx - x))
            if y > cy:
                limits.append((max_y - cy) / (y - cy))
            elif y < cy:
                limits.append(cy / (cy - y))
        return max(0.0, min(limits))

    def scale(self, factor: float) -> MaskRegion:
        if factor == 1.0:
            return self
        cx = sum(point[0] for point in self.polygon) / len(self.polygon)
        cy = sum(point[1] for point in self.polygon) / len(self.polygon)
        scaled = [
            (int(cx + (x - cx) * factor), int(cy + (y - cy) * factor)) for x, y in self.polygon
        ]
        return MaskRegion(polygon=scaled, score=self.score, label=self.label)

    def scale_clamped(self, factor: float, width: int, height: int) -> MaskRegion:
        """均匀放大，但倍率不超过图像边界允许的上限。"""
        if factor == 1.0:
            return self
        effective = min(factor, self.max_uniform_scale(width, height))
        if effective <= 0:
            return self
        return self.scale(effective)

    def clip(self, width: int, height: int) -> MaskRegion:
        clipped = [(max(0, min(width - 1, x)), max(0, min(height - 1, y))) for x, y in self.polygon]
        return MaskRegion(polygon=clipped, score=self.score, label=self.label)


# 兼容旧名称
BBox = MaskRegion
