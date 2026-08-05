"""图片打码流水线。"""

from __future__ import annotations

from pathlib import Path

import imageio.v3 as iio

from media_redact.pipeline.processor import RedactProcessor


def process_image(
    input_path: str | Path,
    output_path: str | Path,
    processor: RedactProcessor,
) -> None:
    frame = iio.imread(str(input_path))
    result = processor.process_frame(frame)
    iio.imwrite(str(output_path), result)
