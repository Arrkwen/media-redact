"""创建 RedactProcessor。"""

from __future__ import annotations

from media_redact.config import MaskMode, MaskShape, RedactConfig
from media_redact.detect.face import FaceDetector
from media_redact.detect.osd import build_osd_detector
from media_redact.model import ensure_face_model, ensure_ocr_models
from media_redact.pipeline.processor import RedactProcessor
from media_redact.paths import TextModelSize


def create_processor(
    *,
    face: bool = False,
    osd_regions: list[str] | None = None,
    osd_bands: list[str] | None = None,
    osd_text_threshold: float = 0.3,
    osd_text_box_threshold: float = 0.5,
    osd_text_rec_threshold: float = 0.0,
    osd_text_model_size: TextModelSize = "small",
    osd_text: list[str] | None = None,
    face_threshold: float = 0.3,
    mask: MaskMode = "mosaic",
    mask_shape: MaskShape = "polygon",
    mask_scale: float = 1.3,
    mosaic_size: int = 20,
    keep_audio: bool = False,
) -> RedactProcessor:
    has_region_osd = bool(osd_regions)
    has_text_osd = bool(osd_text or osd_bands)

    if not face and not has_region_osd and not has_text_osd:
        raise ValueError(
            "At least one of face, osd_regions, osd_bands, or osd_text must be enabled."
        )

    config = RedactConfig(
        mask=mask,
        mask_shape=mask_shape,
        mask_scale=mask_scale,
        face_enabled=face,
        face_threshold=face_threshold,
        osd_enabled=has_region_osd or has_text_osd,
        osd_text_enabled=has_text_osd,
        mosaic_size=mosaic_size,
        keep_audio=keep_audio,
    )

    face_detector = None
    if config.face_enabled:
        face_detector = FaceDetector(
            ensure_face_model(),
            score_threshold=config.face_threshold,
        )

    if has_text_osd:
        ensure_ocr_models(require_rec=bool(osd_text), model_size=osd_text_model_size)

    osd_detector = build_osd_detector(
        osd_regions=osd_regions if has_region_osd else None,
        osd_bands=osd_bands,
        osd_text_threshold=osd_text_threshold,
        osd_text_box_threshold=osd_text_box_threshold,
        osd_text_rec_threshold=osd_text_rec_threshold,
        osd_text_model_size=osd_text_model_size,
        osd_text=osd_text if osd_text else None,
    )

    return RedactProcessor(config, face_detector, osd_detector)
