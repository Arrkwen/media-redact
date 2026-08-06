"""PP-OCRv6 文字 OSD 检测器。"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from media_redact.detect.base import MaskRegion
from media_redact.detect.osd.bands import (
    BandSpec,
    filter_regions_by_bands,
)
from media_redact.detect.osd.db_postprocess import DBPostProcess
from media_redact.detect.osd.onnx_utils import load_onnx_session
from media_redact.detect.osd.text_crop import crop_text_region_perspective
from media_redact.detect.osd.text_filter import TextRegionFilter, boxes_to_mask_regions
from media_redact.detect.osd.text_preprocess import TextDetPreprocess
from media_redact.detect.osd.text_recognizer import TextRecognizer
from media_redact.log import logger


class TextOSDDetector:
    """
    文字 OSD 检测器。

    **``osd_bands`` only** — full-image det → band filter → redact all boxes.

    **``osd_text``** — full-image det → (band filter if set) → OCR → text regex.
    """

    def __init__(
        self,
        det_model_path: str | Path,
        *,
        rec_model_path: str | Path | None = None,
        dict_path: str | Path | None = None,
        bands: list[BandSpec] | None = None,
        score_threshold: float = 0.3,
        box_threshold: float = 0.5,
        rec_score_threshold: float = 0.0,
        unclip_ratio: float = 1.6,
        use_dilation: bool = True,
        pattern_filter: TextRegionFilter | None = None,
        recognizer: TextRecognizer | None = None,
    ) -> None:
        det_path = Path(det_model_path)
        if not det_path.exists():
            raise FileNotFoundError(f"Text detection model not found: {det_path}")

        self._session = load_onnx_session(det_path, model_label="text detection")
        self.input_name = self._session.get_inputs()[0].name
        self.preprocess = TextDetPreprocess()
        self.postprocess = DBPostProcess(
            thresh=score_threshold,
            box_thresh=box_threshold,
            unclip_ratio=unclip_ratio,
            use_dilation=use_dilation,
        )
        self.rec_score_threshold = rec_score_threshold

        use_patterns = bool(pattern_filter and pattern_filter._patterns)
        if use_patterns:
            if recognizer is None:
                if not rec_model_path or not dict_path:
                    raise ValueError(
                        "osd_text requires text_rec.onnx and ppocrv6_dict.txt."
                    )
                recognizer = TextRecognizer(rec_model_path, dict_path)
            self.recognizer = recognizer
            self.pattern_filter = pattern_filter
            self.bands = list(bands) if bands else []
        else:
            if not bands:
                raise ValueError("osd_bands requires at least one band spec.")
            self.recognizer = None
            self.pattern_filter = None
            self.bands = list(bands)

    def detect(self, image: np.ndarray) -> list[MaskRegion]:
        """
        检测文字区域；``osd_text`` 模式下仅返回正则匹配框。

        Pipeline:
            full-image det → (band filter if set)
            → [OCR → text regex when ``osd_text``]
        """
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        elif image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

        regions = self._full_image_det(image)
        logger.debug("OSD text det: {} box(es) after full-image det", len(regions))

        before_band = len(regions)
        regions = self._apply_spatial_filters(image, regions)
        if self.bands:
            logger.debug(
                "OSD text det: {} box(es) after band filter (from {})",
                len(regions),
                before_band,
            )

        if not regions or self.recognizer is None:
            logger.debug("OSD text det: {} box(es) to redact", len(regions))
            return regions

        matched = self._ocr_and_match_regex(image, regions)
        logger.debug(
            "OSD text det: {} box(es) after regex match (from {})",
            len(matched),
            len(regions),
        )
        return matched

    def _full_image_det(self, image_bgr: np.ndarray) -> list[MaskRegion]:
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        model_input = self.preprocess(rgb)
        outputs = self._session.run(None, {self.input_name: model_input})
        boxes, scores = self.postprocess(outputs[0], (image_bgr.shape[0], image_bgr.shape[1]))
        return boxes_to_mask_regions(boxes, scores)

    def _apply_spatial_filters(
        self,
        image: np.ndarray,
        regions: list[MaskRegion],
    ) -> list[MaskRegion]:
        if not regions:
            return regions

        image_h, image_w = image.shape[:2]
        if self.bands:
            regions = filter_regions_by_bands(regions, image_w, image_h, self.bands)
        return regions

    def _ocr_and_match_regex(
        self,
        image: np.ndarray,
        regions: list[MaskRegion],
    ) -> list[MaskRegion]:
        crops = [crop_text_region_perspective(image, region) for region in regions]
        rec_results = self.recognizer.recognize(crops)  # type: ignore[union-attr]

        kept: list[MaskRegion] = []
        for region, (text, rec_score) in zip(regions, rec_results, strict=True):
            if rec_score < self.rec_score_threshold:
                continue
            if not self.pattern_filter.matches_text(text):  # type: ignore[union-attr]
                logger.debug("Skip OSD text box: {!r} (score={:.3f})", text, rec_score)
                continue
            logger.debug("Match OSD text box: {!r} (score={:.3f})", text, rec_score)
            kept.append(region)
        return kept
