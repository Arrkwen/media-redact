"""视频打码流水线。"""

from __future__ import annotations

from pathlib import Path

import imageio
import tqdm

from media_redact.log import logger
from media_redact.pipeline.processor import RedactProcessor


def process_video(
    input_path: str | Path,
    output_path: str | Path,
    processor: RedactProcessor,
    *,
    keep_audio: bool = False,
    ffmpeg_codec: str = "libx264",
    disable_progress: bool = False,
    progress_position: int | None = None,
) -> None:
    input_path = Path(input_path)
    output_path = Path(output_path)
    logger.debug("Open video: {} -> {}", input_path, output_path)

    reader = imageio.get_reader(str(input_path))
    try:
        meta = reader.get_meta_data()
    except Exception as exc:
        raise RuntimeError(f"Cannot open video: {input_path}") from exc

    ffmpeg_config: dict = {"codec": ffmpeg_codec, "fps": meta.get("fps", 25)}
    if keep_audio and meta.get("audio_codec"):
        ffmpeg_config["audio_path"] = str(input_path)
        ffmpeg_config["audio_codec"] = "copy"

    writer = imageio.get_writer(str(output_path), format="FFMPEG", mode="I", **ffmpeg_config)

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

    bar = tqdm.tqdm(**tqdm_kwargs)
    try:
        for frame in reader.iter_data():
            result = processor.process_frame(frame)
            writer.append_data(result)
            bar.update(1)
    finally:
        bar.close()
        reader.close()
        writer.close()

    logger.debug("Video saved: {}", output_path)
