"""检测模块公共导出。"""

from media_redact.detect.base import BBox
from media_redact.detect.face import FaceDetector
from media_redact.detect.osd import RegionOSDDetector

__all__ = ["BBox", "FaceDetector", "RegionOSDDetector"]
