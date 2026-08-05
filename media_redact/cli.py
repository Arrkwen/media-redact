#!/usr/bin/env python3
"""media-redact 命令行入口。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from media_redact import __version__
from media_redact.api import redact_image, redact_video
from media_redact.io.files import get_file_type
from media_redact.log import logger, setup_logging
from media_redact.paths import resolve_input_path, resolve_path


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
        help="Disable progress bars for video and batch processing",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO)",
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(args.log_level, component="media-redact")

    if not args.face and not args.osd:
        logger.error("Specify --face and/or --osd to enable redaction.")
        sys.exit(1)

    if args.osd and not args.osd_region:
        logger.error("--osd requires at least one --osd-region.")
        sys.exit(1)

    try:
        input_path = resolve_input_path(args.input)
    except FileNotFoundError as exc:
        logger.error("{}", exc)
        sys.exit(1)

    filetype = get_file_type(str(input_path))
    if filetype == "notfound":
        logger.error("File not found: {}", input_path)
        sys.exit(1)
    if filetype not in ("image", "video"):
        logger.error("Unsupported file type: {}", input_path)
        sys.exit(1)

    output = Path(args.output) if args.output else None
    if output is not None and not output.is_absolute():
        output = resolve_path(output)

    redact_kwargs = {
        "face": args.face,
        "osd": args.osd,
        "osd_regions": args.osd_region,
        "face_threshold": args.face_threshold,
        "mask": args.mask,
        "mask_shape": args.mask_shape,
        "mask_scale": args.mask_scale,
        "mosaic_size": args.mosaic_size,
        "disable_progress": args.disable_progress,
    }

    try:
        if filetype == "image":
            results = redact_image(input_path, output, **redact_kwargs)
        else:
            results = redact_video(
                input_path,
                output,
                keep_audio=args.keep_audio,
                **redact_kwargs,
            )
    except (ValueError, FileNotFoundError) as exc:
        logger.error("{}", exc)
        sys.exit(1)

    logger.info("Input:  {}", input_path)
    logger.info("Output: {}", results[0])
    logger.success("Done.")


if __name__ == "__main__":
    main()
