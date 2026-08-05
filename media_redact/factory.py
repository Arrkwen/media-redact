"""创建 RedactProcessor。"""

from __future__ import annotations

from media_redact.config import MaskMode, MaskShape, RedactConfig
from media_redact.detect.face import FaceDetector
from media_redact.detect.osd import RegionOSDDetector
from media_redact.paths import DEFAULT_FACE_MODEL
from media_redact.pipeline.processor import RedactProcessor


def create_processor(
    *,
    face: bool = False,
    osd: bool = False,
    osd_regions: list[str] | None = None,
    face_threshold: float = 0.3,
    mask: MaskMode = "mosaic",
    mask_shape: MaskShape = "polygon",
    mask_scale: float = 1.3,
    mosaic_size: int = 20,
    keep_audio: bool = False,
) -> RedactProcessor:
    if not face and not osd:
        raise ValueError("At least one of face=True or osd=True is required.")

    if osd and not osd_regions:
        raise ValueError("osd=True requires osd_regions.")

    config = RedactConfig(
        mask=mask,
        mask_shape=mask_shape,
        mask_scale=mask_scale,
        face_enabled=face,
        face_threshold=face_threshold,
        osd_enabled=osd,
        mosaic_size=mosaic_size,
        keep_audio=keep_audio,
    )

    face_detector = None
    if config.face_enabled:
        if not DEFAULT_FACE_MODEL.exists():
            raise FileNotFoundError(f"Face model not found: {DEFAULT_FACE_MODEL}")
        face_detector = FaceDetector(
            DEFAULT_FACE_MODEL,
            score_threshold=config.face_threshold,
        )

    osd_detector = None
    if config.osd_enabled and osd_regions:
        osd_detector = RegionOSDDetector.from_specs(osd_regions)

    return RedactProcessor(config, face_detector, osd_detector)
