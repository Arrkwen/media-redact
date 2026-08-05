import numpy as np
import pytest
from media_redact.config import RedactConfig
from media_redact.detect.base import MaskRegion
from media_redact.detect.osd import RegionOSDDetector, parse_osd_region
from media_redact.mask.applicator import apply_masks
from media_redact.pipeline.processor import RedactProcessor


def test_mask_region_scale_and_clip():
    region = MaskRegion.from_bbox(10, 10, 30, 30, score=0.9)
    scaled = region.scale(1.5).clip(100, 100)
    x1, _, x2, _ = scaled.bounding_box()
    assert x1 < 10
    assert x2 > 30


def test_parse_osd_region_rect():
    region = parse_osd_region("19,993,480,1079")
    assert region.rect == (19, 993, 480, 1079)


def test_parse_osd_region_polygon():
    region = parse_osd_region("0,900;1920,900;1920,1080;0,1080")
    assert len(region.polygon) == 4


def test_parse_osd_region_invalid():
    with pytest.raises(ValueError):
        parse_osd_region("0,0,1")


def test_region_osd_detector_rect():
    detector = RegionOSDDetector.from_specs(["0,90,200,100"])
    img = np.zeros((100, 200, 3), dtype=np.uint8)
    regions = detector.detect(img)
    assert len(regions) == 1
    _, y1, _, y2 = regions[0].bounding_box()
    assert y1 == 90
    assert y2 == 100


def test_region_osd_detector_polygon():
    detector = RegionOSDDetector.from_specs(["0,0;50,0;50,50;0,50"])
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    regions = detector.detect(img)
    assert regions[0].polygon == [(0, 0), (50, 0), (50, 50), (0, 50)]


def test_apply_mosaic_polygon():
    frame = np.random.randint(0, 255, (80, 80, 3), dtype=np.uint8)
    original = frame.copy()
    region = MaskRegion.from_bbox(10, 10, 50, 50)
    apply_masks(frame, [region], mode="mosaic", mask_shape="polygon", mosaic_size=10)
    assert not np.array_equal(frame[20:40, 20:40], original[20:40, 20:40])


def test_apply_ellipse_differs_from_polygon():
    frame = np.full((60, 60, 3), 128, dtype=np.uint8)
    ellipse_frame = frame.copy()
    polygon_frame = frame.copy()
    region = MaskRegion.from_bbox(10, 10, 50, 50)
    apply_masks(ellipse_frame, [region], mode="solid", mask_shape="ellipse")
    apply_masks(polygon_frame, [region], mode="solid", mask_shape="polygon")
    assert not np.array_equal(ellipse_frame, polygon_frame)


def test_processor_osd_only():
    config = RedactConfig(
        face_enabled=False,
        osd_enabled=True,
        mask="solid",
        mask_shape="polygon",
    )
    osd = RegionOSDDetector.from_specs(["0,0,100,10"])
    processor = RedactProcessor(config, face_detector=None, osd_detector=osd)
    frame = np.full((100, 100, 3), 128, dtype=np.uint8)
    result = processor.process_frame(frame)
    assert np.all(result[0:10, :, :] == 0)
