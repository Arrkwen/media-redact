# User Guide

> **中文**: [USER_GUIDE_CN.md](USER_GUIDE_CN.md)

## Requirements

- Python >= 3.10
- ffmpeg (required for video processing; install separately and ensure it is on `PATH`)

## Installation

```bash
pip install media-redact
```

If the package is not yet on PyPI, install from source:

```bash
pip install /path/to/media-redact          # local directory
# or
pip install git+https://example.com/media-redact.git
```

Two commands are provided after installation:


| Command        | Description                                                             |
| -------------- | ----------------------------------------------------------------------- |
| `media-redact` | Redact images/videos                                                    |
| `media-region` | Web region annotation; generates `--osd-region` / `--osd-band` snippets |


Verify installation:

```bash
media-redact --version
media-region --help
```

Enable `--face` (faces) and/or OSD options explicitly when redacting. 



## Basic Usage

```bash
# Face redaction only
media-redact video.mp4 --face

# Fixed OSD region only (bottom bar polygon, 1920x1080)
media-redact image.jpg \
  --osd-region 0,972;1920,972;1920,1080;0,1080

# Face + fixed OSD (1080p example: bottom-left timestamp regions)
media-redact video.mp4 \
  --face \
  --osd-region 19,993,480,1079 \
  --osd-region 1344,993,1901,1079

# Directory batch (images and videos); default output: ./{dirname}_redacted/
media-redact photos/ --face --recursive

# Directory batch with explicit output directory (preserves subdirectories)
media-redact input_dir/ --face -o output_dir/ --recursive
```

Default output for a **single file**: `{filename}_redacted.{ext}` in the current working directory.

Default output for a **directory**: `{dirname}_redacted/` under the current working directory.

## Redaction Pipeline

```
┌─────────────────┐
│  Input          │  image / video frame (RGB)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  CLI / API      │  create_processor() → RedactProcessor.process_frame()
└────────┬────────┘
         │
         ├──────────────────┬──────────────────┬──────────────────┐
         ▼                  ▼                  ▼                  ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ --face          │ │ --osd-region    │ │ --osd-band      │ │ --osd-text      │
│ FaceDetector    │ │ RegionOSD       │ │ TextOSD         │ │ TextOSD         │
│ YOLO ONNX       │ │ fixed coords    │ │ full-image det  │ │ full-image det  │
│                 │ │ (no model)      │ │ → band filter   │ │ → band filter   │
│                 │ │                 │ │ → all boxes     │ │    if set       │
│                 │ │                 │ │                 │ │ → OCR → regex   │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │                   │
         └───────────────────┴───────────────────┴───────────────────┘
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │  MaskRegion[]       │  merge; skip out-of-bounds
                          └──────────┬──────────┘
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │  apply_masks()      │  blur / mosaic / solid
                          └──────────┬──────────┘
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │  Output             │  redacted image / video
                          └─────────────────────┘
```

## CLI Options

```
usage: media-redact [-h] [-o OUTPUT] [-r]
                    [--face] [--face-threshold FACE_THRESHOLD]
                    [--osd-region SPEC] [--osd-band SPEC] [--osd-text REGEX]
                    ...
                    input
```


| Option               | Default   | Description                                                                          |
| -------------------- | --------- | ------------------------------------------------------------------------------------ |
| `input`              | —         | Input image/video path **or directory**                                              |
| `-o, --output`       | see below | Output **file** (single input) or **directory** (directory input)                    |
| `-r, --recursive`    | false     | Recursively process files in subdirectories                                          |
| `--face`             | false     | Enable face redaction (bundled `media_redact/models/face_det.onnx`)                  |
| `--face-threshold`   | 0.3       | Face detection confidence threshold                                                  |
| `--osd-region`       | —         | Fixed OSD region(s) in absolute pixel coordinates; repeatable                        |
| `--osd-band`         | —         | Text detection band (`top:0.15`, `bottom:0.12`, etc.); repeatable; filters det boxes |
| `--osd-text`         | —         | OCR regex filter; repeatable (OR match)                                              |
| `--mask`             | mosaic    | Mask mode: blur / mosaic / solid / none                                              |
| `--mask-shape`       | polygon   | Region shape: ellipse / polygon                                                      |
| `--mask-scale`       | 1.3       | Face region expansion factor (clamped to image bounds)                               |
| `--mosaic-size`      | 20        | Mosaic block size                                                                    |
| `--keep-audio`       | false     | Preserve original audio for video                                                    |
| `--disable-progress` | false     | Disable frame and batch file progress bars                                           |
| `--log-level`        | INFO      | Log level (DEBUG / INFO / WARNING / ERROR)                                           |


## OSD Region Format

`--osd-region` uses **absolute pixel coordinates**. Specify multiple regions by repeating the flag:


| Format    | Example (1080p)                                | Notes                   |
| --------- | ---------------------------------------------- | ----------------------- |
| Rectangle | `--osd-region 19,993,480,1079`                 | `x1,y1,x2,y2` (pixels)  |
| Polygon   | `--osd-region 0,972;1920,972;1920,1080;0,1080` | Points separated by `;` |


You can **mix** rectangles and polygons in one run—repeat `--osd-region` on the CLI or pass an `osd_regions` list in Python:

```bash
# CLI: one polygon + one rectangle
media-redact image.jpg \
  --osd-region "1138,430;1137,541;959,547;957,660;1257,673;1255,434" \
  --osd-region "27,613,276,679"
```

```python
# Python API
redact_image(
    "image.jpg",
    "out.jpg",
    osd_regions=[
        "1138,430;1137,541;959,547;957,660;1257,673;1255,434",  # polygon
        "27,613,276,679",                                          # rectangle
    ],
)
```

> **Note**: Coordinates are tied to the input image/video resolution. Regions fully outside the image bounds are skipped (not clipped).

Mask shape is controlled by `--mask-shape` (default: `polygon`; also supports `ellipse`).

## OCR Text OSD (`--osd-band` / `--osd-text`)

PP-OCRv5 text detection/recognition without manual coordinates. Download OCR models first:

```bash
python scripts/download_ocr_models.py
```

Both **--osd-band** and **--osd-text** support **repeatable flags** (same as `--osd-region`)—pass a list for multiple bands or regex patterns:


| Option       | Format                                                  | Notes                                                                |
| ------------ | ------------------------------------------------------- | -------------------------------------------------------------------- |
| `--osd-band` | `top:0.15` / `bottom:0.12` / `left:0.08` / `right:0.08` | Top/bottom ratios use image height; left/right use width; repeatable |
| `--osd-text` | Python regex                                            | Enables OCR; redacts only matching boxes; repeatable (**OR** match)  |


```bash
# Redact all text in multiple bands (det-only, no OCR)
media-redact video.mp4 \
  --osd-band top:0.15 \
  --osd-band bottom:0.12 \
  --osd-band left:0.08

# Multiple regex patterns (date or speed)
media-redact video.mp4 \
  --osd-text '\d{4}-\d{2}-\d{2}' \
  --osd-text '\d+\s*km/h'

# Bands + multiple patterns
media-redact video.mp4 \
  --osd-band bottom:0.15 \
  --osd-text '\d{4}-\d{2}-\d{2}' \
  --osd-text 'GPS[:：]\s*\d+'
```

```python
# Python API: pass lists of bands / patterns
redact_video(
    "video.mp4",
    osd_bands=["top:0.15", "bottom:0.12", "right:0.1"],
    osd_text=[r"\d{4}-\d{2}-\d{2}", r"\d+\s*km/h"],
)
```


| Mode                | Behavior                                                                      |
| ------------------- | ----------------------------------------------------------------------------- |
| `--osd-band` only   | Full-image det → band filter → **redact all boxes** (no OCR)                  |
| `--osd-text`        | Full-image det → (band filter if set) → OCR → text regex → **redact matches** |
| `--osd-region` only | Fixed coords → **redact region** (no text det)                                |


## Region Annotator (`media-region`)

When coordinates are unknown, use the web UI to draw rectangles, polygons, or band lines and copy CLI or Python API snippets (default: `http://127.0.0.1:8765`):

```bash
# Start the annotator (upload image/video or enter a stream URL in the page)
media-region

# Preload an image or video
media-region frame.jpg

# Custom port (use with SSH port forwarding on remote hosts)
media-region frame.jpg --port 9000

# Debug RTSP/stream connectivity
media-region --log-level DEBUG
```


| Action               | Description                                                                  |
| -------------------- | ---------------------------------------------------------------------------- |
| Upload image         | Loaded directly in the browser                                               |
| Upload video         | First frame extracted; browser first, then chunked upload or OpenCV fallback |
| Stream URL           | First frame extracted; browser first, then OpenCV backend fallback           |
| Rectangle / `R`      | Click two corners for fixed `--osd-region`                                   |
| Polygon / `P`        | Click vertices for fixed `--osd-region`                                      |
| Band line / `B`      | Click line endpoints to generate `--osd-band` ratios                         |
| Finish polygon / `N` | Close current polygon (≥3 points)                                            |
| Undo / `U`           | Undo last action                                                             |
| Clear / `C`          | Clear all regions (avoid Ctrl+C—it triggers clear)                           |
| Copy CLI             | Copy `media-redact` command snippet                                          |
| Copy API             | Copy Python `redact_image()` call snippet                                    |
| Download coords.txt  | Export CLI and API snippets                                                  |


Use the copied parameters in `media-redact`.

## Python API

You can also call `redact_image()` / `redact_video()` from Python. Inputs may be a single file, multiple files, or a directory (with optional recursive traversal). For batch runs, set `output_dir` as the output root—the **relative subdirectory layout is preserved**, and `_redacted` is appended to each filename.

```python
from media_redact import redact_image, redact_video

# Single image
redact_image("photo.jpg", face=True)

# Explicit output path
redact_image("photo.jpg", "out.jpg", face=True)

# Directory batch (recursive), preserving subdirectories
redact_image(
    "input_dir/",
    output_dir="output_dir/",
    recursive=True,
    face=True,
)

# Multiple files
redact_image(
    ["a.jpg", "b.jpg"],
    output_dir="output_dir/",
    osd_regions=["0,972;1920,972;1920,1080;0,1080"],
)

# Videos work the same way
redact_video(
    "input_videos/",
    output_dir="output_videos/",
    recursive=True,
    face=True,
    keep_audio=True,
)
```

