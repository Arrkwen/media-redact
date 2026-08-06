"""OSD 检测模块。"""

from media_redact.detect.osd.bands import BandSpec, default_bands, parse_osd_band
from media_redact.detect.osd.composite import CompositeOSDDetector, OSDDetector
from media_redact.detect.osd.factory import build_osd_detector
from media_redact.detect.osd.region import OSDRegion, RegionOSDDetector, parse_osd_region
from media_redact.detect.osd.text_detector import TextOSDDetector

__all__ = [
    "BandSpec",
    "CompositeOSDDetector",
    "OSDDetector",
    "OSDRegion",
    "RegionOSDDetector",
    "TextOSDDetector",
    "build_osd_detector",
    "default_bands",
    "parse_osd_band",
    "parse_osd_region",
]
