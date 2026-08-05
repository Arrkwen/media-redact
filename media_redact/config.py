"""配置 dataclass。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MaskMode = Literal["blur", "mosaic", "solid", "none"]
MaskShape = Literal["ellipse", "polygon"]


@dataclass
class RedactConfig:
    face_enabled: bool = False
    face_threshold: float = 0.3
    mask: MaskMode = "mosaic"
    mask_shape: MaskShape = "polygon"
    mask_scale: float = 1.3

    osd_enabled: bool = False

    mosaic_size: int = 20
    keep_audio: bool = False
    ffmpeg_codec: str = "libx264"
