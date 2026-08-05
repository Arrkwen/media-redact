#!/usr/bin/env python3
"""media-redact 命令行入口。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from media_redact import __version__
from media_redact.config import RedactConfig
from media_redact.detect.face import FaceDetector
from media_redact.detect.osd import RegionOSDDetector
from media_redact.io.files import get_file_type
from media_redact.paths import (
    DEFAULT_FACE_MODEL,
    default_output_path,
    resolve_input_path,
    resolve_path,
)
from media_redact.pipeline.image import process_image
from media_redact.pipeline.processor import RedactProcessor
from media_redact.pipeline.video import process_video


def build_processor(args: argparse.Namespace) -> RedactProcessor:
    config = RedactConfig(
        mask=args.mask,
        mask_shape=args.mask_shape,
        mask_scale=args.mask_scale,
        face_enabled=args.face,
        face_threshold=args.face_threshold,
        osd_enabled=args.osd,
        mosaic_size=args.mosaic_size,
        keep_audio=args.keep_audio,
    )

    face_detector = None
    if config.face_enabled:
        if not DEFAULT_FACE_MODEL.exists():
            print(
                f"Error: face model not found: {DEFAULT_FACE_MODEL}",
                file=sys.stderr,
            )
            sys.exit(1)
        face_detector = FaceDetector(
            DEFAULT_FACE_MODEL,
            score_threshold=config.face_threshold,
        )

    osd_detector = None
    if config.osd_enabled and args.osd_region:
        osd_detector = RegionOSDDetector.from_specs(args.osd_region)

    return RedactProcessor(config, face_detector, osd_detector)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Redact faces and OSD regions in images and videos."
    )
    parser.add_argument(
        "input",
        help="Input image or video path (also searches assets/data/)",
    )
    parser.add_argument("-o", "--output", default=None, help="Output path")
    parser.add_argument(
        "--face",
        action="store_true",
        help="Enable face redaction (uses bundled media_redact/models/face_det.onnx)",
    )
    parser.add_argument(
        "--face-threshold",
        type=float,
        default=0.3,
        help="Face detection confidence threshold (default: 0.3)",
    )
    parser.add_argument(
        "--osd",
        action="store_true",
        help="Enable OSD region redaction (requires --osd-region)",
    )
    parser.add_argument(
        "--osd-region",
        action="append",
        default=None,
        metavar="SPEC",
        help=(
            "OSD region in absolute pixel coords. "
            "Rect: x1,y1,x2,y2. Polygon: x1,y1;x2,y2;... "
            "Repeatable."
        ),
    )
    parser.add_argument(
        "--mask",
        default="mosaic",
        choices=["blur", "mosaic", "solid", "none"],
        help="Redaction mask mode (default: mosaic)",
    )
    parser.add_argument(
        "--mask-shape",
        default="polygon",
        choices=["ellipse", "polygon"],
        help="Redaction region shape (default: polygon)",
    )
    parser.add_argument(
        "--mask-scale",
        type=float,
        default=1.3,
        help="Scale factor for redaction masks (default: 1.3)",
    )
    parser.add_argument(
        "--mosaic-size",
        type=int,
        default=20,
        help="Mosaic block size (default: 20)",
    )
    parser.add_argument(
        "--keep-audio",
        action="store_true",
        help="Keep audio track when processing video",
    )
    parser.add_argument(
        "--disable-progress",
        action="store_true",
        help="Disable progress bar for video processing",
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.face and not args.osd:
        print(
            "Error: specify --face and/or --osd to enable redaction.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.osd and not args.osd_region:
        print(
            "Error: --osd requires at least one --osd-region.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        input_path = resolve_input_path(args.input)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    filetype = get_file_type(str(input_path))
    if filetype == "notfound":
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    if filetype not in ("image", "video"):
        print(f"Error: unsupported file type: {input_path}", file=sys.stderr)
        sys.exit(1)

    output = Path(args.output) if args.output else default_output_path(
        input_path)
    if not output.is_absolute():
        output = resolve_path(output)

    processor = build_processor(args)
    print(f"Input:  {input_path}\nOutput: {output}")

    if filetype == "image":
        process_image(input_path, output, processor)
    else:
        process_video(
            input_path,
            output,
            processor,
            keep_audio=args.keep_audio,
            disable_progress=args.disable_progress,
        )

    print("Done.")


if __name__ == "__main__":
    main()
