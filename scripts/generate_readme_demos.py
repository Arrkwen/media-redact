#!/usr/bin/env python3
"""Generate a single README overview image for the four redaction modes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import imageio.v3 as iio
import numpy as np

from media_redact.detect.base import MaskRegion
from media_redact.factory import create_processor
from media_redact.mask.applicator import apply_masks

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/media/demo.jpg"
OUTPUT_PATH = ROOT / "assets/media/demo_redact.jpg"
PREVIEW_WIDTH = 1400
PANEL_GAP = 12
TITLE_HEIGHT = 72
TITLE_FONT_SCALE = 1.15
TITLE_FONT_THICKNESS = 2
CAPTION_FONT_SCALE = 0.72
CAPTION_FONT_THICKNESS = 1
BORDER_COLOR = (0, 0, 255)  # BGR: red
BORDER_THICKNESS = 4


@dataclass(frozen=True)
class DemoPanel:
    title: str
    caption: str
    kwargs: dict


def _write_jpg(path: Path, image: np.ndarray) -> None:
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    elif image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    cv2.imwrite(str(path), image, [int(cv2.IMWRITE_JPEG_QUALITY), 88])


def _load_rgb(path: Path) -> np.ndarray:
    frame = iio.imread(str(path))
    if frame.ndim == 2:
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
    elif frame.shape[2] == 4:
        frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
    return frame


def _scale_region(region: MaskRegion, scale: float) -> MaskRegion:
    if scale == 1.0:
        return region
    scaled_polygon = [(int(x * scale), int(y * scale))
                      for x, y in region.polygon]
    return MaskRegion(polygon=scaled_polygon, score=region.score, label=region.label)


def _collect_masked_regions(processor, bgr: np.ndarray) -> list[MaskRegion]:
    height, width = bgr.shape[:2]
    config = processor.config
    masked: list[MaskRegion] = []

    if config.face_enabled and processor.face_detector is not None:
        for region in processor.face_detector.detect(bgr):
            scaled = region.scale_clamped(config.mask_scale, width, height)
            if scaled.fully_inside(width, height) and len(scaled.polygon) >= 3:
                masked.append(scaled)

    if config.osd_enabled and processor.osd_detector is not None:
        for region in processor.osd_detector.detect(bgr):
            if region.fully_inside(width, height) and len(region.polygon) >= 3:
                masked.append(region)

    return masked


def _draw_border(bgr: np.ndarray, region: MaskRegion) -> None:
    polygon = np.array(region.polygon, dtype=np.int32).reshape(-1, 1, 2)
    cv2.polylines(
        bgr,
        [polygon],
        isClosed=True,
        color=BORDER_COLOR,
        thickness=BORDER_THICKNESS,
        lineType=cv2.LINE_AA,
    )


def _render_panel(frame_rgb: np.ndarray, panel: DemoPanel, tile_width: int) -> np.ndarray:
    frame = frame_rgb.copy()
    processor = create_processor(**panel.kwargs)
    bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    regions = _collect_masked_regions(processor, bgr)
    if not regions:
        raise RuntimeError(
            f"No redaction regions detected for panel: {panel.title}")

    apply_masks(
        frame,
        regions,
        mode="mosaic",
        mask_shape="polygon",
        mask_scale=1.0,
        mosaic_size=20,
    )

    masked_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    height, width = masked_bgr.shape[:2]
    scale = tile_width / width
    tile = cv2.resize(
        masked_bgr,
        (tile_width, int(height * scale)),
        interpolation=cv2.INTER_AREA,
    )

    for region in regions:
        _draw_border(tile, _scale_region(region, scale))
    return tile


def _add_title_bar(tile: np.ndarray, title: str, caption: str) -> np.ndarray:
    label_bar = np.full((TITLE_HEIGHT, tile.shape[1], 3), 255, dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(
        label_bar,
        title,
        (10, 30),
        font,
        TITLE_FONT_SCALE,
        (20, 20, 20),
        TITLE_FONT_THICKNESS,
        cv2.LINE_AA,
    )
    cv2.putText(
        label_bar,
        caption,
        (10, 58),
        font,
        CAPTION_FONT_SCALE,
        (90, 90, 90),
        CAPTION_FONT_THICKNESS,
        cv2.LINE_AA,
    )
    return np.vstack([label_bar, tile])


def _build_overview(panels: list[np.ndarray], demos: list[DemoPanel]) -> np.ndarray:
    labeled = [
        _add_title_bar(tile, panel.title, panel.caption)
        for tile, panel in zip(panels, demos, strict=True)
    ]
    gap_v = np.full((labeled[0].shape[0], PANEL_GAP, 3), 255, dtype=np.uint8)
    gap_h = np.full(
        (PANEL_GAP, labeled[0].shape[1] * 2 + PANEL_GAP, 3), 255, dtype=np.uint8)
    top = np.hstack([labeled[0], gap_v, labeled[1]])
    bottom = np.hstack([labeled[2], gap_v, labeled[3]])
    overview = np.vstack([top, gap_h, bottom])

    height, width = overview.shape[:2]
    if width <= PREVIEW_WIDTH:
        return overview
    scale = PREVIEW_WIDTH / width
    return cv2.resize(
        overview,
        (PREVIEW_WIDTH, int(height * scale)),
        interpolation=cv2.INTER_AREA,
    )


def _demo_panels() -> list[DemoPanel]:
    osd_region = "2680,90,2939,239"
    osd_band = "bottom:0.12"
    osd_text = r"^USB.*$"

    return [
        DemoPanel(
            title="Face redaction",
            caption="--face",
            kwargs={"face": True},
        ),
        DemoPanel(
            title="Fixed OSD regions",
            caption=f"--osd-region {osd_region}",
            kwargs={"osd_regions": [osd_region]},
        ),
        DemoPanel(
            title="Band OSD regions",
            caption=f"--osd-band {osd_band}",
            kwargs={"osd_bands": [osd_band]},
        ),
        DemoPanel(
            title="OSD text regex match",
            caption=f"--osd-text '{osd_text}'",
            kwargs={"osd_text": [osd_text]},
        ),
    ]


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit(f"Sample image not found: {SOURCE}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame_rgb = _load_rgb(SOURCE)
    demos = _demo_panels()
    tile_width = (PREVIEW_WIDTH - PANEL_GAP) // 2

    panels = [_render_panel(frame_rgb, panel, tile_width) for panel in demos]
    overview = _build_overview(panels, demos)
    _write_jpg(OUTPUT_PATH, overview)
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
