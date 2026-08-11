"""图片打码流水线。"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

import imageio.v3 as iio
import numpy as np

from media_redact.log import logger
from media_redact.pipeline.frame_pipeline import (
    DEFAULT_IO_QUEUE_SIZE,
    DEFAULT_NUM_WORKER,
    FrameTask,
    run_frame_pipeline,
)
from media_redact.pipeline.processor import RedactProcessor


class _ImageBatchSink:
    def prepare(self) -> None:
        return None

    def write(self, index: int, frame: np.ndarray, context: object) -> None:
        output_path = Path(context)  # type: ignore[arg-type]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        iio.imwrite(str(output_path), frame)
        logger.debug("Image saved: {}", output_path)

    def close(self) -> None:
        return None


def _iter_image_tasks(
    pairs: Sequence[tuple[Path, Path]],
) -> Iterator[FrameTask]:
    for index, (input_path, output_path) in enumerate(pairs):
        logger.debug("Open image: {} -> {}", input_path, output_path)
        frame = iio.imread(str(input_path))
        yield FrameTask(index, frame, output_path)


def process_images(
    pairs: Sequence[tuple[Path, Path]],
    processor: RedactProcessor,
    *,
    num_worker: int = DEFAULT_NUM_WORKER,
    queue_size: int = DEFAULT_IO_QUEUE_SIZE,
    on_frame_done: Callable[[], None] | None = None,
) -> None:
    if not pairs:
        return
    run_frame_pipeline(
        _iter_image_tasks(pairs),
        _ImageBatchSink(),
        processor,
        num_worker=num_worker,
        queue_size=queue_size,
        ordered_output=False,
        on_frame_done=on_frame_done,
    )


def process_image(
    input_path: str | Path,
    output_path: str | Path,
    processor: RedactProcessor,
    *,
    num_worker: int = DEFAULT_NUM_WORKER,
    queue_size: int = DEFAULT_IO_QUEUE_SIZE,
) -> None:
    process_images(
        [(Path(input_path), Path(output_path))],
        processor,
        num_worker=num_worker,
        queue_size=queue_size,
    )
