"""Tests for OCR OSD text detection + recognition pipeline."""

import numpy as np
import pytest
from media_redact.detect.base import MaskRegion
from media_redact.detect.osd.bands import (
    crop_band,
    filter_regions_by_bands,
    parse_osd_band,
    region_in_band,
)
from media_redact.detect.osd.composite import CompositeOSDDetector
from media_redact.detect.osd.db_postprocess import DBPostProcess
from media_redact.detect.osd.region import RegionOSDDetector
from media_redact.detect.osd.text_filter import TextFilterConfig, TextRegionFilter
from media_redact.detect.osd.text_preprocess import TextDetPreprocess
from media_redact.detect.osd.text_rec_postprocess import CTCLabelDecode
from media_redact.factory import create_processor
from media_redact.paths import default_text_det_model, default_text_dict, default_text_rec_model


def test_parse_osd_band():
    band = parse_osd_band("top:0.15")
    assert band.name == "top"
    assert band.ratio == 0.15

    left = parse_osd_band("left:0.08")
    assert left.name == "left"
    assert left.ratio == 0.08


def test_crop_band_bottom():
    image = np.zeros((100, 200, 3), dtype=np.uint8)
    crop, offset_x, offset_y = crop_band(image, parse_osd_band("bottom:0.1"))
    assert crop.shape == (10, 200, 3)
    assert offset_y == 90


def test_region_in_band_uses_center_y():
    top = parse_osd_band("top:0.2")
    bottom = parse_osd_band("bottom:0.2")
    height = 100
    width = 200

    in_top = MaskRegion.from_rect((0, 5, 100, 15), label="osd_text")
    in_bottom = MaskRegion.from_rect((0, 88, 100, 98), label="osd_text")
    in_middle = MaskRegion.from_rect((0, 45, 100, 55), label="osd_text")

    assert region_in_band(in_top, width, height, top)
    assert not region_in_band(in_top, width, height, bottom)
    assert region_in_band(in_bottom, width, height, bottom)
    assert not region_in_band(in_middle, width, height, top)
    assert not region_in_band(in_middle, width, height, bottom)


def test_region_in_band_supports_left_right():
    left = parse_osd_band("left:0.2")
    right = parse_osd_band("right:0.2")
    width = 200
    height = 100

    in_left = MaskRegion.from_rect((5, 40, 30, 60), label="osd_text")
    in_right = MaskRegion.from_rect((170, 40, 195, 60), label="osd_text")
    in_center = MaskRegion.from_rect((90, 40, 110, 60), label="osd_text")

    assert region_in_band(in_left, width, height, left)
    assert region_in_band(in_right, width, height, right)
    assert not region_in_band(in_center, width, height, left)
    assert not region_in_band(in_center, width, height, right)


def test_filter_regions_by_bands():
    bands = [parse_osd_band("top:0.2"), parse_osd_band("bottom:0.2")]
    regions = [
        MaskRegion.from_rect((0, 5, 100, 15), label="osd_text"),
        MaskRegion.from_rect((0, 45, 100, 55), label="osd_text"),
        MaskRegion.from_rect((0, 88, 100, 98), label="osd_text"),
    ]
    kept = filter_regions_by_bands(regions, 200, 100, bands)
    assert len(kept) == 2
    assert kept[0].polygon == regions[0].polygon
    assert kept[1].polygon == regions[2].polygon


def test_text_osd_detector_pattern_mode_without_bands(tmp_path, monkeypatch):
    from media_redact.detect.osd.text_detector import TextOSDDetector

    det_path = tmp_path / "det.onnx"
    det_path.write_bytes(b"dummy")

    class FakeDetSession:
        def get_inputs(self):
            class Input:
                name = "x"

            return [Input()]

    monkeypatch.setattr(
        "media_redact.detect.osd.text_detector.load_onnx_session",
        lambda _path, model_label=None: FakeDetSession(),
    )

    detector = TextOSDDetector(
        det_model_path=det_path,
        rec_model_path=tmp_path / "rec.onnx",
        dict_path=tmp_path / "dict.txt",
        pattern_filter=TextRegionFilter(TextFilterConfig(patterns=[r".*"])),
        recognizer=type("FakeRecognizer", (), {"recognize": lambda self, crops: [("x", 1.0)] * len(crops)})(),
    )
    assert detector.bands == []


def test_text_osd_detector_runs_det_once_for_multiple_bands(tmp_path, monkeypatch):
    from media_redact.detect.osd.text_detector import TextOSDDetector

    det_path = tmp_path / "det.onnx"
    det_path.write_bytes(b"dummy")
    run_count = 0

    class FakeDetSession:
        def get_inputs(self):
            class Input:
                name = "x"

            return [Input()]

        def run(self, *_args, **_kwargs):
            nonlocal run_count
            run_count += 1
            return [np.zeros((1, 1, 32, 32), dtype=np.float32)]

    monkeypatch.setattr(
        "media_redact.detect.osd.text_detector.load_onnx_session",
        lambda _path, model_label=None: FakeDetSession(),
    )
    monkeypatch.setattr(
        "media_redact.detect.osd.text_detector.DBPostProcess.__call__",
        lambda self, _pred, _shape: (np.zeros((0, 4, 2), dtype=np.float32), []),
    )

    detector = TextOSDDetector(
        det_model_path=det_path,
        bands=[parse_osd_band("top:0.15"), parse_osd_band("bottom:0.12")],
    )
    image = np.full((200, 320, 3), 255, dtype=np.uint8)
    detector.detect(image)
    assert run_count == 1


def test_db_postprocess_on_synthetic_blob():
    post = DBPostProcess(thresh=0.5, box_thresh=0.5, use_dilation=False)
    pred = np.zeros((1, 1, 32, 32), dtype=np.float32)
    pred[0, 0, 10:20, 8:24] = 0.9
    boxes, scores = post(pred, (32, 32))
    assert len(boxes) >= 1


def test_text_preprocess_output_shape():
    image = np.zeros((90, 120, 3), dtype=np.uint8)
    tensor = TextDetPreprocess()(image)
    assert tensor.shape[0] == 1
    assert tensor.shape[2] % 32 == 0


def test_text_region_filter_pattern_match():
    filt = TextRegionFilter(TextFilterConfig(patterns=[r"\d{4}-\d{2}-\d{2}", r"\d+ km/h"]))
    assert filt.matches_text("2024-08-06")
    assert filt.matches_text("80 km/h")
    assert not filt.matches_text("hello")


def test_ctc_decoder_loads_dict():
    dict_path_obj = default_text_dict()
    if not dict_path_obj.exists():
        pytest.skip("ppocrv6_dict.txt not downloaded")
    decoder = CTCLabelDecode(dict_path_obj)
    assert "blank" in decoder.character
    assert len(decoder.character) > 1000


def test_build_osd_detector_osd_text_keeps_fixed_region_mask(tmp_path, monkeypatch):
    from media_redact.detect.osd.factory import build_osd_detector

    det_path = tmp_path / "det.onnx"
    rec_path = tmp_path / "rec.onnx"
    dict_path = tmp_path / "dict.txt"
    det_path.write_bytes(b"dummy")
    rec_path.write_bytes(b"dummy")
    dict_path.write_text("a\n")

    class FakeDetSession:
        def get_inputs(self):
            class Input:
                name = "x"

            return [Input()]

    class FakeRecognizer:
        def recognize(self, crops):
            return [("x", 1.0) for _ in crops]

    monkeypatch.setattr(
        "media_redact.detect.osd.factory.paths.default_text_det_model",
        lambda _size="small": det_path,
    )
    monkeypatch.setattr(
        "media_redact.detect.osd.factory.paths.default_text_rec_model",
        lambda _size="small": rec_path,
    )
    monkeypatch.setattr("media_redact.detect.osd.factory.paths.default_text_dict", lambda: dict_path)
    monkeypatch.setattr(
        "media_redact.detect.osd.text_detector.load_onnx_session",
        lambda _path, model_label=None: FakeDetSession(),
    )
    monkeypatch.setattr(
        "media_redact.detect.osd.text_detector.TextRecognizer",
        lambda *args, **kwargs: FakeRecognizer(),
    )

    composite = build_osd_detector(
        osd_text=[r"\d+"],
        osd_regions=["0,0,50,50"],
    )
    assert composite.region_detector is not None
    assert composite.text_detector is not None
    assert composite.text_detector.bands == []


def test_text_osd_detector_pipeline_order(tmp_path, monkeypatch):
    from media_redact.detect.osd.text_detector import TextOSDDetector

    det_path = tmp_path / "det.onnx"
    det_path.write_bytes(b"dummy")
    calls: list[str] = []

    class FakeDetSession:
        def get_inputs(self):
            class Input:
                name = "x"

            return [Input()]

        def run(self, *_args, **_kwargs):
            return [np.zeros((1, 1, 32, 32), dtype=np.float32)]

    class FakeRecognizer:
        def recognize(self, crops):
            calls.append("ocr")
            return [("2024-08-06", 0.99) for _ in crops]

    monkeypatch.setattr(
        "media_redact.detect.osd.text_detector.load_onnx_session",
        lambda _path, model_label=None: FakeDetSession(),
    )

    detector = TextOSDDetector(
        det_model_path=det_path,
        pattern_filter=TextRegionFilter(TextFilterConfig(patterns=[r"\d{4}-\d{2}-\d{2}"])),
        recognizer=FakeRecognizer(),
        bands=[parse_osd_band("bottom:0.5")],
    )

    inside = MaskRegion.from_rect((10, 180, 20, 195), label="osd_text")
    outside = MaskRegion.from_rect((150, 150, 170, 170), label="osd_text")

    def fake_full_image_det(_image):
        calls.append("det")
        return [inside, outside]

    def fake_apply_spatial_filters(_image, regions):
        calls.append("spatial")
        return [inside]

    monkeypatch.setattr(detector, "_full_image_det", fake_full_image_det)
    monkeypatch.setattr(detector, "_apply_spatial_filters", fake_apply_spatial_filters)

    image = np.full((200, 200, 3), 255, dtype=np.uint8)
    result = detector.detect(image)

    assert calls == ["det", "spatial", "ocr"]
    assert result == [inside]


def test_text_osd_detector_apply_spatial_filters():
    from media_redact.detect.osd.text_detector import TextOSDDetector

    detector = TextOSDDetector.__new__(TextOSDDetector)
    detector.bands = [parse_osd_band("bottom:0.5")]
    image = np.full((200, 200, 3), 255, dtype=np.uint8)

    in_band = MaskRegion.from_rect((10, 180, 20, 195), label="osd_text")
    out_band = MaskRegion.from_rect((10, 10, 20, 25), label="osd_text")
    assert detector._apply_spatial_filters(image, [in_band, out_band]) == [in_band]

    detector.bands = []
    assert detector._apply_spatial_filters(image, [in_band, out_band]) == [in_band, out_band]


def test_composite_osd_detector_merges_region_and_text():
    region_detector = RegionOSDDetector.from_specs(["0,0,10,10"])

    class FakeTextDetector:
        def detect(self, image):
            return [MaskRegion.from_rect((20, 20, 30, 30), label="osd_text")]

    composite = CompositeOSDDetector(
        region_detector=region_detector,
        text_detector=FakeTextDetector(),
    )
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    regions = composite.detect(image)
    assert len(regions) == 2


def test_create_processor_osd_band_requires_det_model(tmp_path, monkeypatch):
    missing = tmp_path / "missing.onnx"
    monkeypatch.setattr("media_redact.factory.ensure_ocr_models", lambda **kwargs: None)
    monkeypatch.setattr(
        "media_redact.detect.osd.factory.paths.default_text_det_model",
        lambda _size="small": missing,
    )
    with pytest.raises(FileNotFoundError, match="Text detection model"):
        create_processor(osd_bands=["bottom:0.12"])


def test_create_processor_osd_text_requires_models(tmp_path, monkeypatch):
    missing = tmp_path / "missing.onnx"
    monkeypatch.setattr("media_redact.factory.ensure_ocr_models", lambda **kwargs: None)
    monkeypatch.setattr(
        "media_redact.detect.osd.factory.paths.default_text_det_model",
        lambda _size="small": missing,
    )
    with pytest.raises(FileNotFoundError, match="Text detection model"):
        create_processor(osd_text=[r"\d+"])


def test_text_osd_detector_band_only_returns_all_boxes(tmp_path, monkeypatch):
    from media_redact.detect.osd.bands import parse_osd_band
    from media_redact.detect.osd.text_detector import TextOSDDetector

    det_path = tmp_path / "det.onnx"
    det_path.write_bytes(b"dummy")

    class FakeDetSession:
        def get_inputs(self):
            class Input:
                name = "x"

            return [Input()]

    monkeypatch.setattr(
        "media_redact.detect.osd.text_detector.load_onnx_session",
        lambda _path, model_label=None: FakeDetSession(),
    )

    detector = TextOSDDetector(
        det_model_path=det_path,
        bands=[parse_osd_band("bottom:0.5")],
    )
    region = MaskRegion.from_rect((10, 180, 200, 195), label="osd_text")
    monkeypatch.setattr(detector, "_full_image_det", lambda image: [region])

    image = np.full((200, 320, 3), 255, dtype=np.uint8)
    assert len(detector.detect(image)) == 1


def test_text_osd_detector_rec_and_pattern_filter(tmp_path, monkeypatch):
    from media_redact.detect.osd.text_detector import TextOSDDetector

    det_path = tmp_path / "det.onnx"
    rec_path = tmp_path / "rec.onnx"
    dict_path = tmp_path / "dict.txt"
    det_path.write_bytes(b"dummy")
    rec_path.write_bytes(b"dummy")
    dict_path.write_text("a\n")

    class FakeDetSession:
        def get_inputs(self):
            class Input:
                name = "x"

            return [Input()]

    class FakeRecognizer:
        def recognize(self, crops):
            return [("2024-08-06", 0.99) for _ in crops]

    monkeypatch.setattr(
        "media_redact.detect.osd.text_detector.load_onnx_session",
        lambda _path, model_label=None: FakeDetSession(),
    )

    detector = TextOSDDetector(
        det_model_path=det_path,
        rec_model_path=rec_path,
        dict_path=dict_path,
        pattern_filter=TextRegionFilter(TextFilterConfig(patterns=[r"\d{4}-\d{2}-\d{2}"])),
        recognizer=FakeRecognizer(),
    )
    region = MaskRegion.from_rect((10, 180, 200, 195), label="osd_text")
    monkeypatch.setattr(detector, "_full_image_det", lambda image: [region])

    image = np.full((200, 320, 3), 255, dtype=np.uint8)
    assert len(detector.detect(image)) == 1

    detector.pattern_filter = TextRegionFilter(TextFilterConfig(patterns=[r"nomatch"]))
    assert detector.detect(image) == []


@pytest.mark.skipif(
    not (
        default_text_det_model().exists()
        and default_text_rec_model().exists()
        and default_text_dict().exists()
    ),
    reason="OCR models not downloaded",
)
def test_text_osd_detector_end_to_end_blank():
    from media_redact.detect.osd.text_detector import TextOSDDetector

    try:
        detector = TextOSDDetector(
            det_model_path=default_text_det_model(),
            rec_model_path=default_text_rec_model(),
            dict_path=default_text_dict(),
            bands=[parse_osd_band("bottom:0.2")],
            pattern_filter=TextRegionFilter(TextFilterConfig(patterns=[r".*"])),
        )
    except RuntimeError as exc:
        pytest.skip(str(exc))

    image = np.full((480, 640, 3), 128, dtype=np.uint8)
    regions = detector.detect(image)
    assert isinstance(regions, list)
