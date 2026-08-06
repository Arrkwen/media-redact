"""Python API：单文件、多文件与目录批量打码。"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal

import tqdm

from media_redact.config import MaskMode, MaskShape
from media_redact.factory import create_processor
from media_redact.io.files import get_file_type
from media_redact.log import ensure_logging, logger
from media_redact.paths import default_output_path
from media_redact.pipeline.image import process_image
from media_redact.pipeline.processor import RedactProcessor
from media_redact.pipeline.video import process_video

InputSpec = str | Path | Sequence[str | Path]
MediaKind = Literal["image", "video"]

__all__ = [
    "InputSpec",
    "redact_image",
    "redact_video",
]


def _normalize_inputs(inputs: InputSpec) -> list[Path]:
    if isinstance(inputs, (str, Path)):
        return [Path(inputs)]
    return [Path(item) for item in inputs]


def _common_root(paths: Sequence[Path]) -> Path:
    resolved = [path.resolve() for path in paths]
    if len(resolved) == 1:
        path = resolved[0]
        return path if path.is_dir() else path.parent

    parts_list = [path.parts for path in resolved]
    common: list[str] = []
    for group in zip(*parts_list, strict=False):
        if len(set(group)) == 1:
            common.append(group[0])
        else:
            break
    if not common:
        raise ValueError("Cannot infer a common input root for the given paths.")
    return Path(*common)


def _collect_files(
    inputs: InputSpec,
    media_kind: MediaKind,
    *,
    recursive: bool,
) -> tuple[list[Path], Path, bool]:
    roots: list[Path] = []
    files: list[Path] = []
    has_directory_input = False

    for raw in _normalize_inputs(inputs):
        path = raw.expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Input not found: {path}")

        if path.is_dir():
            has_directory_input = True
            roots.append(path.resolve())
            iterator = path.rglob("*") if recursive else path.iterdir()
            for candidate in iterator:
                if candidate.is_file() and get_file_type(str(candidate)) == media_kind:
                    files.append(candidate.resolve())
            continue

        if not path.is_file():
            raise ValueError(f"Input is not a file or directory: {path}")

        file_type = get_file_type(str(path))
        if file_type != media_kind:
            raise ValueError(f"Expected {media_kind} input, got {file_type or 'unknown'}: {path}")
        files.append(path.resolve())
        roots.append(path.parent.resolve())

    if not files:
        label = "images" if media_kind == "image" else "videos"
        raise FileNotFoundError(f"No {label} found in the given inputs.")

    unique_files = sorted(set(files))
    input_root = _common_root(roots)
    return unique_files, input_root, has_directory_input


def _redacted_name(path: Path) -> str:
    return f"{path.stem}_redacted{path.suffix}"


def _resolve_output_path(
    input_file: Path,
    input_root: Path,
    *,
    output: Path | None,
    output_dir: Path | None,
    single_input: bool,
) -> Path:
    if single_input and output is not None:
        return output.expanduser().resolve()

    if output_dir is not None:
        output_root = output_dir.expanduser().resolve()
        relative = input_file.relative_to(input_root)
        return output_root / relative.parent / _redacted_name(input_file)

    if not single_input:
        raise ValueError("output_dir is required when processing multiple inputs.")

    return default_output_path(input_file)


def _validate_output_args(
    input_files: Sequence[Path],
    *,
    output: Path | None,
    output_dir: Path | None,
    has_directory_input: bool,
) -> None:
    if len(input_files) > 1 and output is not None:
        raise ValueError(
            "output applies to a single input only; use output_dir for batch processing."
        )
    if (has_directory_input or len(input_files) > 1) and output_dir is None:
        raise ValueError(
            "output_dir is required when input is a directory or contains multiple files."
        )


def _run_redact(
    input_files: Sequence[Path],
    input_root: Path,
    output_paths: Sequence[Path],
    processor: RedactProcessor,
    *,
    media_kind: MediaKind,
    keep_audio: bool,
    disable_progress: bool,
) -> list[Path]:
    ensure_logging()
    batch_mode = len(input_files) > 1
    label = "images" if media_kind == "image" else "videos"
    logger.info("Found {} {} to process", len(input_files), label)

    pairs = list(zip(input_files, output_paths, strict=True))
    iterator: Iterable[tuple[Path, Path]] = pairs
    file_bar: tqdm.tqdm | None = None

    if batch_mode and not disable_progress:
        file_bar = tqdm.tqdm(
            total=len(pairs),
            desc=f"Redacting {label}",
            unit="file",
            dynamic_ncols=True,
        )

    results: list[Path] = []
    try:
        for index, (input_file, output_file) in enumerate(iterator, start=1):
            if file_bar is not None:
                file_bar.set_description(f"Redacting {label} ({index}/{len(input_files)})")
                file_bar.refresh()

            output_file.parent.mkdir(parents=True, exist_ok=True)
            if media_kind == "image":
                process_image(input_file, output_file, processor)
            else:
                process_video(
                    input_file,
                    output_file,
                    processor,
                    keep_audio=keep_audio,
                    disable_progress=disable_progress or batch_mode,
                    progress_position=1 if batch_mode and not disable_progress else None,
                )
            results.append(output_file)
            if file_bar is not None:
                file_bar.update(1)
    finally:
        if file_bar is not None:
            file_bar.close()

    logger.info("Completed {} file(s)", len(results))
    return results


def redact_image(
    inputs: InputSpec,
    output: str | Path | None = None,
    *,
    output_dir: str | Path | None = None,
    recursive: bool = False,
    face: bool = False,
    osd_regions: list[str] | None = None,
    osd_bands: list[str] | None = None,
    osd_text_threshold: float = 0.3,
    osd_text_box_threshold: float = 0.5,
    osd_text_rec_threshold: float = 0.0,
    osd_text: list[str] | None = None,
    face_threshold: float = 0.3,
    mask: MaskMode = "mosaic",
    mask_shape: MaskShape = "polygon",
    mask_scale: float = 1.3,
    mosaic_size: int = 20,
    disable_progress: bool = False,
) -> list[Path]:
    """
    对图片打码。支持单文件、多文件或目录；目录可递归处理。

    批量处理时通过 ``output_dir`` 指定输出根目录，保留相对 ``input_root`` 的子目录结构，
    文件名追加 ``_redacted`` 后缀。
    """
    input_files, input_root, has_directory_input = _collect_files(
        inputs, "image", recursive=recursive
    )
    out = Path(output) if output is not None else None
    out_dir = Path(output_dir) if output_dir is not None else None
    _validate_output_args(
        input_files,
        output=out,
        output_dir=out_dir,
        has_directory_input=has_directory_input,
    )

    single_input = len(input_files) == 1
    output_paths = [
        _resolve_output_path(
            input_file,
            input_root,
            output=out,
            output_dir=out_dir,
            single_input=single_input,
        )
        for input_file in input_files
    ]

    processor = create_processor(
        face=face,
        osd_regions=osd_regions,
        osd_bands=osd_bands,
        osd_text_threshold=osd_text_threshold,
        osd_text_box_threshold=osd_text_box_threshold,
        osd_text_rec_threshold=osd_text_rec_threshold,
        osd_text=osd_text,
        face_threshold=face_threshold,
        mask=mask,
        mask_shape=mask_shape,
        mask_scale=mask_scale,
        mosaic_size=mosaic_size,
    )
    return _run_redact(
        input_files,
        input_root,
        output_paths,
        processor,
        media_kind="image",
        keep_audio=False,
        disable_progress=disable_progress,
    )


def redact_video(
    inputs: InputSpec,
    output: str | Path | None = None,
    *,
    output_dir: str | Path | None = None,
    recursive: bool = False,
    face: bool = False,
    osd_regions: list[str] | None = None,
    osd_bands: list[str] | None = None,
    osd_text_threshold: float = 0.3,
    osd_text_box_threshold: float = 0.5,
    osd_text_rec_threshold: float = 0.0,
    osd_text: list[str] | None = None,
    face_threshold: float = 0.3,
    mask: MaskMode = "mosaic",
    mask_shape: MaskShape = "polygon",
    mask_scale: float = 1.3,
    mosaic_size: int = 20,
    keep_audio: bool = False,
    disable_progress: bool = False,
) -> list[Path]:
    """
    对视频打码。支持单文件、多文件或目录；目录可递归处理。

    批量处理时通过 ``output_dir`` 指定输出根目录，保留相对 ``input_root`` 的子目录结构，
    文件名追加 ``_redacted`` 后缀。
    """
    input_files, input_root, has_directory_input = _collect_files(
        inputs, "video", recursive=recursive
    )
    out = Path(output) if output is not None else None
    out_dir = Path(output_dir) if output_dir is not None else None
    _validate_output_args(
        input_files,
        output=out,
        output_dir=out_dir,
        has_directory_input=has_directory_input,
    )

    single_input = len(input_files) == 1
    output_paths = [
        _resolve_output_path(
            input_file,
            input_root,
            output=out,
            output_dir=out_dir,
            single_input=single_input,
        )
        for input_file in input_files
    ]

    processor = create_processor(
        face=face,
        osd_regions=osd_regions,
        osd_bands=osd_bands,
        osd_text_threshold=osd_text_threshold,
        osd_text_box_threshold=osd_text_box_threshold,
        osd_text_rec_threshold=osd_text_rec_threshold,
        osd_text=osd_text,
        face_threshold=face_threshold,
        mask=mask,
        mask_shape=mask_shape,
        mask_scale=mask_scale,
        mosaic_size=mosaic_size,
        keep_audio=keep_audio,
    )
    return _run_redact(
        input_files,
        input_root,
        output_paths,
        processor,
        media_kind="video",
        keep_audio=keep_audio,
        disable_progress=disable_progress,
    )
