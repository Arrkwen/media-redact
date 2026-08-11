"""统一帧处理流水线：生产 → 线程池打码 → 写入。"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from queue import Queue
from threading import Thread
from typing import Protocol

import numpy as np

from media_redact.pipeline.processor import RedactProcessor

DEFAULT_IO_QUEUE_SIZE = 4
DEFAULT_NUM_WORKER = max(1, min(4, os.cpu_count() or 1))

_POISON = object()


@dataclass(frozen=True)
class FrameTask:
    index: int
    frame: np.ndarray
    context: object = None


class FrameSink(Protocol):
    def prepare(self) -> None: ...

    def write(self, index: int, frame: np.ndarray, context: object) -> None: ...

    def close(self) -> None: ...


def run_frame_pipeline(
    tasks: Iterator[FrameTask],
    sink: FrameSink,
    processor: RedactProcessor,
    *,
    num_worker: int = DEFAULT_NUM_WORKER,
    queue_size: int = DEFAULT_IO_QUEUE_SIZE,
    ordered_output: bool = True,
    on_frame_done: Callable[[], None] | None = None,
) -> None:
    """运行帧流水线；``num_worker > 1`` 时启用并行流水线，否则顺序处理。"""
    num_worker = max(1, num_worker)
    if num_worker <= 1:
        _run_sequential(tasks, sink, processor, on_frame_done=on_frame_done)
        return

    _run_pipelined(
        tasks,
        sink,
        processor,
        worker_count=num_worker,
        queue_size=max(1, queue_size),
        ordered_output=ordered_output,
        on_frame_done=on_frame_done,
    )


def _run_sequential(
    tasks: Iterator[FrameTask],
    sink: FrameSink,
    processor: RedactProcessor,
    *,
    on_frame_done: Callable[[], None] | None,
) -> None:
    sink.prepare()
    try:
        for task in tasks:
            result = processor.process_frame(task.frame)
            sink.write(task.index, result, task.context)
            if on_frame_done is not None:
                on_frame_done()
    finally:
        sink.close()


def _run_pipelined(
    tasks: Iterator[FrameTask],
    sink: FrameSink,
    processor: RedactProcessor,
    *,
    worker_count: int,
    queue_size: int,
    ordered_output: bool,
    on_frame_done: Callable[[], None] | None,
) -> None:
    job_queue: Queue = Queue(maxsize=queue_size)
    result_queue: Queue = Queue(maxsize=queue_size)
    errors: list[BaseException] = []
    total_tasks = [-1]

    def _record_error(exc: BaseException) -> None:
        if not errors:
            errors.append(exc)
        for _ in range(worker_count):
            job_queue.put(_POISON)
        result_queue.put(_POISON)

    def _producer() -> None:
        count = 0
        try:
            for task in tasks:
                job_queue.put(task)
                count += 1
            total_tasks[0] = count
            for _ in range(worker_count):
                job_queue.put(_POISON)
        except BaseException as exc:
            total_tasks[0] = count
            _record_error(exc)

    def _worker() -> None:
        try:
            while True:
                task = job_queue.get()
                if task is _POISON:
                    break
                assert isinstance(task, FrameTask)
                result = processor.process_frame(task.frame)
                result_queue.put(
                    FrameTask(task.index, result, task.context)
                )
        except BaseException as exc:
            _record_error(exc)

    def _writer() -> None:
        def _flush_pending() -> None:
            nonlocal written, next_index
            while next_index in pending:
                item = pending.pop(next_index)
                sink.write(item.index, item.frame, item.context)
                next_index += 1
                written += 1
                if on_frame_done is not None:
                    on_frame_done()

        try:
            sink.prepare()
            written = 0
            pending: dict[int, FrameTask] = {}
            next_index = 0
            while True:
                if total_tasks[0] >= 0:
                    if ordered_output:
                        _flush_pending()
                    if written >= total_tasks[0]:
                        break
                result = result_queue.get()
                if result is _POISON:
                    break
                assert isinstance(result, FrameTask)
                if ordered_output:
                    pending[result.index] = result
                    _flush_pending()
                else:
                    sink.write(result.index, result.frame, result.context)
                    written += 1
                    if on_frame_done is not None:
                        on_frame_done()
        except BaseException as exc:
            _record_error(exc)
        finally:
            sink.close()

    producer_thread = Thread(
        target=_producer,
        name="media-redact-producer",
        daemon=True,
    )
    writer_thread = Thread(
        target=_writer,
        name="media-redact-writer",
        daemon=True,
    )
    worker_threads = [
        Thread(
            target=_worker,
            name=f"media-redact-worker-{index}",
            daemon=True,
        )
        for index in range(worker_count)
    ]

    producer_thread.start()
    writer_thread.start()
    for thread in worker_threads:
        thread.start()

    producer_thread.join()
    for thread in worker_threads:
        thread.join()
    writer_thread.join()

    if errors:
        raise errors[0]
