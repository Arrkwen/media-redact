# User Guide

> **中文**: [USER_GUIDE_CN.md](USER_GUIDE_CN.md)

## Overview

`media-redact` redacts faces and on-screen overlay (OSD) content in images and videos. Detection and masking are decoupled—enable one or more modes per run.


| Mode              | Flag           | When to use                                                 |
| ----------------- | -------------- | ----------------------------------------------------------- |
| Face redaction    | `--face`       | Auto-detect and redact faces                                |
| Fixed OSD regions | `--osd-region` | Redact known rectangles/polygons (absolute pixel coords)    |
| Band OSD          | `--osd-band`   | Redact all detected text inside top/bottom/left/right bands |
| OSD text regex    | `--osd-text`   | OCR + redact only boxes matching regex patterns             |


At least one of `--face`, `--osd-region`, `--osd-band`, or `--osd-text` must be enabled.

## Requirements

- Python >= 3.10
- ffmpeg (video processing; install separately and ensure it is on `PATH`)

## Installation

```bash
pip install media-redact
```

Install from source if the package is not yet on PyPI:

```bash
pip install /path/to/media-redact
# or
pip install git+https://example.com/media-redact.git
```


| Command        | Description                                                     |
| -------------- | --------------------------------------------------------------- |
| `media-redact` | Redact images/videos                                            |
| `media-region` | Web annotator; generates `--osd-region` / `--osd-band` snippets |


```bash
media-redact --version
media-region --help
```

The face model (`face_det.onnx`) and OCR assets are cached under `**~/.media_redact/models/**` by default and **downloaded automatically on first use** (not bundled in the wheel). Override the location with `MEDIA_REDACT_MODEL_ROOT`.

## Quick Start

```bash
# Face
media-redact video.mp4 --face

# Fixed OSD region (1080p bottom bar polygon)
media-redact image.jpg --osd-region 0,972;1920,972;1920,1080;0,1080

# Band OSD (all text in bottom 12%)
media-redact video.mp4 --osd-band bottom:0.12

# Text regex (dates only)
media-redact video.mp4 --osd-text '\d{4}-\d{2}-\d{2}'

# Combine modes
media-redact video.mp4 --face --osd-region 19,993,480,1079 --osd-band bottom:0.12

# Directory batch
media-redact photos/ --face -r
media-redact input_dir/ --face -o output_dir/ -r
```

**Output defaults**


| Input       | Default output                                                    |
| ----------- | ----------------------------------------------------------------- |
| Single file | `./{filename}_redacted.{ext}`                                     |
| Directory   | `./{dirname}_redacted/` (preserves subdirectory layout with `-r`) |


For a single file, `-o` is an output **file**; for a directory, `-o` is an output **directory**.

## Redaction Modes

### Face (`--face`)

ONNX face detection with configurable mask mode and expansion:

```bash
media-redact video.mp4 --face --face-threshold 0.3 --mask-scale 1.3
```

### Fixed OSD regions (`--osd-region`)

Redact user-defined regions in **absolute pixel coordinates**. Repeat the flag for multiple regions; rectangles and polygons can be mixed.


| Format    | Example (1080p)                                | Syntax                  |
| --------- | ---------------------------------------------- | ----------------------- |
| Rectangle | `--osd-region 19,993,480,1079`                 | `x1,y1,x2,y2`           |
| Polygon   | `--osd-region 0,972;1920,972;1920,1080;0,1080` | points separated by `;` |


```bash
media-redact image.jpg \
  --osd-region "1138,430;1137,541;959,547;957,660;1257,673;1255,434" \
  --osd-region "27,613,276,679"
```

Coordinates are tied to input resolution. Regions fully outside the image are **skipped** (not clipped). Shape is controlled by `--mask-shape` (`polygon` default, or `ellipse`).

### Band OSD (`--osd-band`)

Full-image text detection, then keep boxes whose center falls in the specified bands. **All remaining boxes are redacted** (no OCR).


| Band         | Example                   | Ratio relative to |
| ------------ | ------------------------- | ----------------- |
| Top / bottom | `top:0.15`, `bottom:0.12` | image height      |
| Left / right | `left:0.08`, `right:0.08` | image width       |


```bash
media-redact video.mp4 \
  --osd-band top:0.15 \
  --osd-band bottom:0.12
```

### OSD text regex (`--osd-text`)

Full-image text detection → optional band filter → OCR → regex match. Only matching boxes are redacted.

```bash
# Whole frame
media-redact video.mp4 --osd-text '\d{4}-\d{2}-\d{2}'

# Limit OCR to a band
media-redact video.mp4 \
  --osd-band bottom:0.15 \
  --osd-text '\d{4}-\d{2}-\d{2}' \
  --osd-text 'GPS[:：]\s*\d+'
```

Multiple `--osd-text` patterns use **OR** matching.


| Configuration       | Pipeline                                                             |
| ------------------- | -------------------------------------------------------------------- |
| `--osd-band` only   | full-image det → band filter → redact all boxes                      |
| `--osd-text`        | full-image det → (band filter if set) → OCR → regex → redact matches |
| `--osd-region` only | fixed coords → redact region (no text det)                           |


## CLI Reference

```
usage: media-redact [-h] [-o OUTPUT] [-r]
                    [--face] [--face-threshold FACE_THRESHOLD]
                    [--osd-region SPEC] [--osd-band SPEC] [--osd-text REGEX]
                    [--mask {blur,mosaic,solid,none}] [--mask-shape {ellipse,polygon}]
                    ...
                    input
```


| Option                     | Default   | Description                                                   |
| -------------------------- | --------- | ------------------------------------------------------------- |
| `input`                    | —         | Image/video path or directory                                 |
| `-o, --output`             | see above | Output file (single input) or directory (directory input)     |
| `-r, --recursive`          | false     | Recurse into subdirectories                                   |
| `--face`                   | false     | Enable face redaction                                         |
| `--face-threshold`         | 0.3       | Face detection confidence threshold                           |
| `--osd-region`             | —         | Fixed OSD region(s); repeatable                               |
| `--osd-band`               | —         | Text detection band; repeatable                               |
| `--osd-text`               | —         | OCR regex filter; repeatable (OR match)                       |
| `--osd-text-threshold`     | 0.3       | Text probability map threshold                                |
| `--osd-text-box-threshold` | 0.5       | Text box score threshold                                      |
| `--osd-text-rec-threshold` | 0.0       | Minimum OCR confidence                                        |
| `--osd-text-model-size`    | small     | PP-OCRv6 text det/rec model size: `tiny` / `small` / `medium` |
| `--mask`                   | mosaic    | `blur` / `mosaic` / `solid` / `none`                          |
| `--mask-shape`             | polygon   | `ellipse` / `polygon`                                         |
| `--mask-scale`             | 1.3       | Face region expansion (clamped to image bounds)               |
| `--mosaic-size`            | 20        | Mosaic block size                                             |
| `--keep-audio`             | false     | Preserve original audio for video                             |
| `--disable-progress`       | false     | Disable progress bars                                         |
| `--log-level`              | INFO      | `DEBUG` / `INFO` / `WARNING` / `ERROR`                        |


## Region Annotator (`media-region`)

When coordinates are unknown, draw regions or band lines in a browser and copy CLI / API snippets (default: `http://127.0.0.1:8765`):

```bash
media-region                  # open annotator
media-region frame.jpg        # preload image or video
media-region frame.jpg --port 9000
```


| Action                  | Description                                |
| ----------------------- | ------------------------------------------ |
| Rectangle / `R`         | Two clicks → `--osd-region`                |
| Polygon / `P`           | Vertices → `--osd-region`; finish with `N` |
| Band line / `B`         | Line endpoints → `--osd-band` ratio        |
| Undo / `U`, Clear / `C` | Undo last action / clear all               |
| Copy CLI / Copy API     | Copy ready-to-run snippets                 |


## Python API

```python
redact_image(
    inputs,
    output=None,
    *,
    output_dir=None,
    recursive=False,
    face=False,
    face_threshold=0.3,
    osd_regions=None,
    osd_bands=None,
    osd_text=None,
    osd_text_threshold=0.3,
    osd_text_box_threshold=0.5,
    osd_text_rec_threshold=0.0,
    osd_text_model_size="small",
    mask="mosaic",
    mask_shape="polygon",
    mask_scale=1.3,
    mosaic_size=20,
    disable_progress=False,
)

redact_video(..., keep_audio=False)  # same kwargs as redact_image
```

```python
from media_redact import redact_image, redact_video
# from media_redact.log import setup_logging
# setup_logging("INFO")  # DEBUG / INFO / WARNING / ERROR


# Single file
redact_image("photo.jpg", face=True)
redact_image("photo.jpg", "out.jpg", face=True)

# Directory batch (use output_dir; preserves layout)
redact_image(
    "input_dir/",
    output_dir="output_dir/",
    recursive=True,
    face=True,
    face_threshold=0.3,
)

# Multiple files
redact_image(
    ["a.jpg", "b.jpg"],
    output_dir="output_dir/",
    osd_regions=["0,972;1920,972;1920,1080;0,1080"],
)

# Video
redact_video(
    "input_videos/",
    output_dir="output_videos/",
    recursive=True,
    face=True,
    osd_bands=["bottom:0.12"],
    osd_text=[r"\d{4}-\d{2}-\d{2}"],
    keep_audio=True,
)
```

CLI uses `-o` for both file and directory output; the Python API uses `output` (single file) and `output_dir` (batch).

## Further Reading

- [Developer Guide](DEVELOPER_GUIDE.md) — project layout, pipeline diagrams, tests, and demo image generation

