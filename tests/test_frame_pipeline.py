"""Tests for unified frame pipeline."""

import numpy as np
import pytest
from media_redact.pipeline.frame_pipeline import FrameTask, run_frame_pipeline


class _ListSink:
    def __init__(self) -> None:
        self.frames: list[np.ndarray] = []
        self.contexts: list[object] = []

    def prepare(self) -> None:
        return None

    def write(self, index: int, frame: np.ndarray, context: object) -> None:
        self.frames.append(frame)
        self.contexts.append(context)

    def close(self) -> None:
        return None


class _FakeProcessor:
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        return frame + 1


def _tasks(count: int) -> list[FrameTask]:
    return [
        FrameTask(index, np.array([index], dtype=np.uint8))
        for index in range(count)
    ]


def test_run_frame_pipeline_preserves_order():
    sink = _ListSink()
    processor = _FakeProcessor()

    run_frame_pipeline(
        iter(_tasks(5)),
        sink,
        processor,
        num_worker=2,
        queue_size=2,
        ordered_output=True,
    )

    assert len(sink.frames) == 5
    assert [int(frame[0]) for frame in sink.frames] == [1, 2, 3, 4, 5]


def test_run_frame_pipeline_unordered_output():
    sink = _ListSink()
    processor = _FakeProcessor()

    run_frame_pipeline(
        iter(_tasks(3)),
        sink,
        processor,
        num_worker=2,
        queue_size=2,
        ordered_output=False,
    )

    assert len(sink.frames) == 3
    assert sorted(int(frame[0]) for frame in sink.frames) == [1, 2, 3]


def test_run_frame_pipeline_empty_tasks():
    sink = _ListSink()
    processor = _FakeProcessor()

    run_frame_pipeline(
        iter([]),
        sink,
        processor,
        num_worker=2,
        queue_size=2,
    )

    assert sink.frames == []


def test_run_frame_pipeline_propagates_producer_error():
    class _BrokenTasks:
        def __iter__(self):
            yield FrameTask(0, np.zeros((1,), dtype=np.uint8))
            raise RuntimeError("read failed")

    sink = _ListSink()
    processor = _FakeProcessor()

    with pytest.raises(RuntimeError, match="read failed"):
        run_frame_pipeline(
            _BrokenTasks(),
            sink,
            processor,
            num_worker=2,
            queue_size=2,
        )


def test_run_frame_pipeline_sequential_when_num_worker_is_one():
    sink = _ListSink()
    processor = _FakeProcessor()

    run_frame_pipeline(
        iter(_tasks(3)),
        sink,
        processor,
        num_worker=1,
    )

    assert [int(frame[0]) for frame in sink.frames] == [1, 2, 3]
