"""视频打码流水线。"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import imageio
import tqdm

from media_redact.log import logger
from media_redact.pipeline.frame_pipeline import (
    DEFAULT_IO_QUEUE_SIZE,
    DEFAULT_NUM_WORKER,
    FrameTask,
    run_frame_pipeline,
)
from media_redact.pipeline.processor import RedactProcessor


class _VideoFrameSink:
    def __init__(self, writer: imageio.core.Format.Writer) -> None:
        self._writer = writer

    def prepare(self) -> None:
        return None

    def write(self, index: int, frame: object, context: object) -> None:
        self._writer.append_data(frame)  # type: ignore[arg-type]

    def close(self) -> None:
        return None


def _iter_video_tasks(reader: imageio.core.Format.Reader) -> Iterator[FrameTask]:
    for index, frame in enumerate(reader.iter_data()):
        yield FrameTask(index, frame)


def process_video(
    input_path: str | Path,
    output_path: str | Path,
    processor: RedactProcessor,
    *,
    keep_audio: bool = False,
    ffmpeg_codec: str = "libx264",
    disable_progress: bool = False,
    progress_position: int | None = None,
    num_worker: int = DEFAULT_NUM_WORKER,
    io_queue_size: int = DEFAULT_IO_QUEUE_SIZE,
    on_frame_done: Callable[[], None] | None = None,
) -> None:
    input_path = Path(input_path)
    output_path = Path(output_path)
    logger.debug(
        "Open video: {} -> {} (num_worker={})",
        input_path,
        output_path,
        num_worker,
    )

    reader = imageio.get_reader(str(input_path))
    try:
        meta = reader.get_meta_data()
    except Exception as exc:
        reader.close()
        raise RuntimeError(f"Cannot open video: {input_path}") from exc

    ffmpeg_config: dict = {"codec": ffmpeg_codec, "fps": meta.get("fps", 25)}
    if keep_audio and meta.get("audio_codec"):
        ffmpeg_config["audio_path"] = str(input_path)
        ffmpeg_config["audio_codec"] = "copy"

    writer = imageio.get_writer(str(output_path), format="FFMPEG", mode="I", **ffmpeg_config)

    progress_bar = None
    if on_frame_done is None and not disable_progress:
        try:
            nframes = reader.count_frames()
        except Exception:
            nframes = None
        tqdm_kwargs: dict = {
            "total": nframes,
            "disable": disable_progress,
            "dynamic_ncols": True,
            "desc": input_path.name,
            "unit": "frame",
            "leave": progress_position is None,
        }
        if progress_position is not None:
            tqdm_kwargs["position"] = progress_position
        progress_bar = tqdm.tqdm(**tqdm_kwargs)
        on_frame_done = progress_bar.update

    try:
        run_frame_pipeline(
            _iter_video_tasks(reader),
            _VideoFrameSink(writer),
            processor,
            num_worker=num_worker,
            queue_size=io_queue_size,
            ordered_output=True,
            on_frame_done=on_frame_done,
        )
    finally:
        if progress_bar is not None:
            progress_bar.close()
        reader.close()
        writer.close()

    logger.debug("Video saved: {}", output_path)
