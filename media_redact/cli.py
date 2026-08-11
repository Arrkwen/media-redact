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
from media_redact.paths import resolve_input_path, resolve_output_dir
from media_redact.pipeline.frame_pipeline import DEFAULT_NUM_WORKER

_BATCH_EMPTY_IMAGE_MSG = "No images found in the given inputs."
_BATCH_EMPTY_VIDEO_MSG = "No videos found in the given inputs."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Redact faces and OSD regions in images and videos."
    )
    parser.add_argument(
        "input",
        help="Input image/video path or directory (also searches assets/data/)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output directory (default: ./output_redact)",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively process files in subdirectories",
    )
    parser.add_argument(
        "--face",
        action="store_true",
        help="Enable face redaction (auto-downloads face_det.onnx to ~/.media_redact/models/)",
    )
    parser.add_argument(
        "--face-threshold",
        type=float,
        default=0.3,
        help="Face detection confidence threshold (default: 0.3)",
    )
    parser.add_argument(
        "--osd-region",
        action="append",
        default=None,
        metavar="SPEC",
        help=(
            "Fixed OSD region in absolute pixel coords; repeatable. "
            "Rect: x1,y1,x2,y2. Polygon: x1,y1;x2,y2;..."
        ),
    )
    parser.add_argument(
        "--osd-band",
        action="append",
        default=None,
        metavar="SPEC",
        help=(
            "Limit text detection to image bands; repeatable. "
            "Formats: top:0.15, bottom:0.12, left:0.08, right:0.08. "
            "Det-only redaction in bands, or combine with --osd-text for OCR filter"
        ),
    )
    parser.add_argument(
        "--osd-text",
        action="append",
        required=False,
        default=None,
        metavar="REGEX",
        help=(
            "Enable text det+OCR; redact boxes whose recognized text matches REGEX; "
            "repeatable for multiple patterns (OR match)"
        ),
    )
    parser.add_argument(
        "--osd-text-threshold",
        type=float,
        default=0.3,
        help="Text probability map threshold (default: 0.3)",
    )
    parser.add_argument(
        "--osd-text-box-threshold",
        type=float,
        default=0.5,
        help="Text box score threshold (default: 0.5)",
    )
    parser.add_argument(
        "--osd-text-rec-threshold",
        type=float,
        default=0.0,
        help="Minimum recognition confidence to consider a text box (default: 0.0)",
    )
    parser.add_argument(
        "--osd-text-model-size",
        default="small",
        choices=["tiny", "small", "medium"],
        help="PP-OCRv6 text det/rec model size (default: small)",
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
        "--device",
        default="auto",
        choices=["auto", "cpu", "cuda"],
        help="ONNX Runtime device: auto (prefer CUDA), cpu, or cuda (default: auto)",
    )
    parser.add_argument(
        "--num-worker",
        type=int,
        default=DEFAULT_NUM_WORKER,
        metavar="N",
        help=(
            "Worker count for redaction pipeline; >1 enables pipelined IO "
            f"(default: {DEFAULT_NUM_WORKER})"
        ),
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


def _redact_directory(
    input_path: Path,
    *,
    output: Path,
    recursive: bool,
    redact_kwargs: dict,
    keep_audio: bool,
) -> list[Path]:
    results: list[Path] = []
    batch_kwargs = {
        **redact_kwargs,
        "output": output,
        "recursive": recursive,
    }
    try:
        results.extend(redact_image(input_path, **batch_kwargs))
    except FileNotFoundError as exc:
        if str(exc) != _BATCH_EMPTY_IMAGE_MSG:
            raise

    try:
        results.extend(
            redact_video(
                input_path,
                keep_audio=keep_audio,
                **batch_kwargs,
            )
        )
    except FileNotFoundError as exc:
        if str(exc) != _BATCH_EMPTY_VIDEO_MSG:
            raise

    if not results:
        raise FileNotFoundError(f"No images or videos found in: {input_path}")

    return results


def main() -> None:
    args = parse_args()
    setup_logging(args.log_level, component="media-redact")

    if not args.face and not args.osd_region and not args.osd_text and not args.osd_band:
        logger.error(
            "Specify --face, --osd-region, --osd-band, and/or --osd-text to enable redaction."
        )
        sys.exit(1)

    try:
        input_path = resolve_input_path(args.input)
        output = resolve_output_dir(args.output)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("{}", exc)
        sys.exit(1)

    redact_kwargs = {
        "face": args.face,
        "osd_regions": args.osd_region,
        "osd_bands": args.osd_band,
        "osd_text_threshold": args.osd_text_threshold,
        "osd_text_box_threshold": args.osd_text_box_threshold,
        "osd_text_rec_threshold": args.osd_text_rec_threshold,
        "osd_text_model_size": args.osd_text_model_size,
        "osd_text": args.osd_text,
        "face_threshold": args.face_threshold,
        "mask": args.mask,
        "mask_shape": args.mask_shape,
        "mask_scale": args.mask_scale,
        "mosaic_size": args.mosaic_size,
        "device": args.device,
        "disable_progress": args.disable_progress,
        "num_worker": args.num_worker,
    }

    try:
        if input_path.is_dir():
            results = _redact_directory(
                input_path,
                output=output,
                recursive=args.recursive,
                redact_kwargs=redact_kwargs,
                keep_audio=args.keep_audio,
            )
        else:
            filetype = get_file_type(str(input_path))
            if filetype not in ("image", "video"):
                logger.error("Unsupported file type: {}", input_path)
                sys.exit(1)

            if filetype == "image":
                results = redact_image(
                    input_path,
                    output,
                    recursive=args.recursive,
                    **redact_kwargs,
                )
            else:
                results = redact_video(
                    input_path,
                    output,
                    recursive=args.recursive,
                    keep_audio=args.keep_audio,
                    **redact_kwargs,
                )
    except (ValueError, FileNotFoundError) as exc:
        logger.error("{}", exc)
        sys.exit(1)

    logger.info("Input:  {}", input_path)
    logger.info("Output dir: {}", output)
    if len(results) != 1:
        logger.info("Processed {} file(s)", len(results))
    else:
        logger.info("Output file: {}", results[0])
    logger.success("Done.")


if __name__ == "__main__":
    main()
