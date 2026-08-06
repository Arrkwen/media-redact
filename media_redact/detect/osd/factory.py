"""构建 OSD 检测器。"""

from __future__ import annotations

from pathlib import Path

from media_redact import paths
from media_redact.detect.osd.bands import parse_osd_band
from media_redact.detect.osd.composite import CompositeOSDDetector
from media_redact.detect.osd.text_detector import TextOSDDetector
from media_redact.detect.osd.text_filter import TextFilterConfig, TextRegionFilter


def build_osd_detector(
    *,
    osd_regions: list[str] | None = None,
    osd_bands: list[str] | None = None,
    osd_text_threshold: float = 0.3,
    osd_text_box_threshold: float = 0.5,
    osd_text_rec_threshold: float = 0.0,
    osd_text: list[str] | None = None,
    text_det_model_path: Path | None = None,
    text_rec_model_path: Path | None = None,
    text_dict_path: Path | None = None,
) -> CompositeOSDDetector | None:
    has_pattern_osd = bool(osd_text)
    has_band_osd = bool(osd_bands)
    has_text_osd = has_pattern_osd or has_band_osd
    if not osd_regions and not has_text_osd:
        return None

    text_detector = None
    if has_text_osd:
        band_specs = [parse_osd_band(spec) for spec in osd_bands] if osd_bands else None
        pattern_filter = (
            TextRegionFilter(TextFilterConfig(patterns=osd_text))
            if has_pattern_osd
            else None
        )
        text_detector = TextOSDDetector(
            det_model_path=text_det_model_path or paths.default_text_det_model(),
            rec_model_path=text_rec_model_path or paths.default_text_rec_model(),
            dict_path=text_dict_path or paths.default_text_dict(),
            bands=band_specs,
            score_threshold=osd_text_threshold,
            box_threshold=osd_text_box_threshold,
            rec_score_threshold=osd_text_rec_threshold,
            pattern_filter=pattern_filter,
        )

    return CompositeOSDDetector.from_parts(
        region_specs=osd_regions,
        text_detector=text_detector,
    )
