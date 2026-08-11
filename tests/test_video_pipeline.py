"""Tests for video frame pipeline integration."""

import numpy as np
import pytest
from media_redact.pipeline.frame_pipeline import FrameTask, run_frame_pipeline


class _FakeReader:
    def __init__(self, frames: list[np.ndarray]):
        self._frames = frames

    def iter_data(self):
        yield from self._frames


class _FakeWriter:
    def __init__(self):
        self.frames: list[np.ndarray] = []

    def append_data(self, frame: np.ndarray) -> None:
        self.frames.append(frame)


class _FakeProcessor:
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        return frame + 1


class _VideoSink:
    def __init__(self, writer: _FakeWriter) -> None:
        self._writer = writer

    def prepare(self) -> None:
        return None

    def write(self, index: int, frame: np.ndarray, context: object) -> None:
        self._writer.append_data(frame)

    def close(self) -> None:
        return None


def _iter_video_tasks(reader: _FakeReader):
    for index, frame in enumerate(reader.iter_data()):
        yield FrameTask(index, frame)


def test_video_pipeline_preserves_order():
    frames = [np.array([i], dtype=np.uint8) for i in range(5)]
    reader = _FakeReader(frames)
    writer = _FakeWriter()
    processor = _FakeProcessor()

    run_frame_pipeline(
        _iter_video_tasks(reader),
        _VideoSink(writer),
        processor,
        num_worker=2,
        queue_size=2,
        ordered_output=True,
    )

    assert len(writer.frames) == 5
    assert [int(frame[0]) for frame in writer.frames] == [1, 2, 3, 4, 5]


def test_video_pipeline_propagates_reader_error():
    class _BrokenReader:
        def iter_data(self):
            yield np.zeros((1,), dtype=np.uint8)
            raise RuntimeError("read failed")

    writer = _FakeWriter()
    processor = _FakeProcessor()

    with pytest.raises(RuntimeError, match="read failed"):
        run_frame_pipeline(
            _iter_video_tasks(_BrokenReader()),
            _VideoSink(writer),
            processor,
            num_worker=2,
            queue_size=2,
            ordered_output=True,
        )
