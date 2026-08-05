# media-redact

> **中文文档**：[docs/README_CN.md](docs/README_CN.md)

Face and on-screen overlay (OSD) redaction for images and videos.

Detect and redact faces in images and videos, or redact fixed OSD regions (timestamps, GPS, device IDs, etc.). Detection and masking are decoupled—enable face and/or OSD processing as needed.

## Features

- **Face redaction**: ONNX-based detection with blur / mosaic / solid
- **OSD redaction**: Fixed regions via CLI (absolute pixel coordinates)
- **Region annotation**: Companion web tool `media-region` for drawing regions in a browser

---

## User Guide

### Requirements

- Python >= 3.10
- ffmpeg (required for video processing; install separately and ensure it is on `PATH`)

### Installation

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


| Command        | Description                                                 |
| -------------- | ----------------------------------------------------------- |
| `media-redact` | Redact images/videos                                        |
| `media-region` | Web region annotation; generates `--osd-region` coordinates |


Verify installation:

```bash
media-redact --version
media-region --help
```

Enable `--face` (faces) and/or `--osd` (fixed regions) explicitly when redacting. The face model is bundled with the package (`media_redact/models/face_det.onnx`)—no extra setup required.

### Basic Usage

```bash
# Face redaction only
media-redact video.mp4 --face

# OSD redaction only (bottom bar polygon, 1920x1080)
media-redact image.jpg \
  --osd \
  --osd-region 0,972;1920,972;1920,1080;0,1080

# Face + OSD (1080p example: bottom-left timestamp regions)
media-redact video.mp4 \
  --face \
  --osd \
  --osd-region 19,993,480,1079 \
  --osd-region 1344,993,1901,1079

# Custom output path
media-redact video.mp4 --face -o output.mp4

# Keep original audio for video
media-redact video.mp4 --face --keep-audio
```

Default output: `{filename}_redacted.{ext}` in the current working directory.

### CLI Options

```
usage: media-redact [-h] [-o OUTPUT]
                    [--face] [--face-threshold FACE_THRESHOLD]
                    [--osd] [--osd-region SPEC]
                    [--mask {blur,mosaic,solid,none}]
                    [--mask-shape {ellipse,polygon}]
                    [--mask-scale MASK_SCALE] [--mosaic-size MOSAIC_SIZE]
                    [--keep-audio] [--disable-progress]
                    [--log-level {DEBUG,INFO,WARNING,ERROR}] [--version]
                    input
```


| Option             | Default   | Description                                                         |
| ------------------ | --------- | ------------------------------------------------------------------- |
| `input`            | —         | Input image or video path                                           |
| `-o, --output`     | see below | Output path; default `{stem}_redacted{ext}`                         |
| `--face`           | false     | Enable face redaction (bundled `media_redact/models/face_det.onnx`) |
| `--face-threshold` | 0.3       | Face detection confidence threshold                                 |
| `--osd`            | false     | Enable OSD region redaction (requires `--osd-region`)               |
| `--osd-region`     | —         | OSD region(s) in absolute pixel coordinates; repeatable             |
| `--mask`           | mosaic    | Mask mode: blur / mosaic / solid / none                             |
| `--mask-shape`     | polygon   | Region shape: ellipse / polygon                                     |
| `--mask-scale`     | 1.3       | Face region expansion factor                                        |
| `--mosaic-size`    | 20        | Mosaic block size                                                   |
| `--keep-audio` | false | Preserve original audio for video |
| `--disable-progress` | false | Disable frame and batch file progress bars |
| `--log-level` | INFO | Log level (DEBUG / INFO / WARNING / ERROR) |


### OSD Region Format

`--osd-region` uses **absolute pixel coordinates**. Specify multiple regions by repeating the flag:


| Format    | Example (1080p)                                | Notes                   |
| --------- | ---------------------------------------------- | ----------------------- |
| Rectangle | `--osd-region 19,993,480,1079`                 | `x1,y1,x2,y2` (pixels)  |
| Polygon   | `--osd-region 0,972;1920,972;1920,1080;0,1080` | Points separated by `;` |


> **Note**: Coordinates are tied to the input image/video resolution. Re-specify regions when the resolution changes.

Mask shape is controlled by `--mask-shape` (default: `polygon`; also supports `ellipse`).

### Region Annotator (`media-region`)

When coordinates are unknown, use the web UI to draw rectangles or polygons and copy `--osd-region` values (default: `http://127.0.0.1:8765`):

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
| Rectangle / `R`      | Click two opposite corners                                                   |
| Polygon / `P`        | Click vertices                                                               |
| Finish polygon / `N` | Close current polygon (≥3 points)                                            |
| Undo / `U`           | Undo last action                                                             |
| Clear / `C`          | Clear all regions                                                            |
| Copy command         | Copy `--osd-region` snippet                                                  |
| Download coords.txt  | Export coordinates file                                                      |


Use the copied parameters with `--osd` in `media-redact`.

### Python API

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
    osd=True,
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

---

## Developer Guide

For contributors running tests and developing locally. [uv](https://docs.astral.sh/uv/) is recommended for dependency and virtualenv management.

### Requirements

- Python >= 3.10
- [uv](https://docs.astral.sh/uv/) (recommended)
- ffmpeg

### Clone and Sync

```bash
git clone <repo-url> media-redact
cd media-redact
uv sync --group dev
```

This will:

- Create a project virtual environment (`.venv/`)
- Install dependencies from `uv.lock`
- Install the package in editable mode

### Resources

`media_redact/models/face_det.onnx` is the face detection model and **must be included in release builds**. Optional test data lives under `assets/data/` at the repo root:

```bash
media_redact/
└── models/face_det.onnx   # Face model (bundled in releases)

assets/
└── data/                  # Sample inputs (optional, not packaged)
```

### Run and Test

```bash
# Redact (use uv run in development)
uv run media-redact assets/data/video.mp4 \
  --face \
  --osd \
  --osd-region 19,993,480,1079 \
  --mask-shape polygon

# Region annotation
uv run media-region assets/data/frame.jpg

# Tests
uv run pytest

# Lint
uv run ruff check media_redact tests
uv run ruff format --check media_redact tests
```

After activating the virtual environment:

```bash
source .venv/bin/activate
media-redact --help
media-region --help
pytest
```

### Common uv Commands


| Command                   | Description                                  |
| ------------------------- | -------------------------------------------- |
| `uv sync`                 | Sync production deps and install the package |
| `uv sync --group dev`     | Sync production + dev dependencies           |
| `uv run media-redact ...` | Run CLI in the project environment           |
| `uv run pytest`           | Run tests                                    |
| `uv run ruff check .`     | Lint code                                    |
| `uv run ruff format .`    | Format code                                  |
| `uv add <package>`        | Add a dependency                             |
| `uv lock`                 | Update the lockfile                          |


### Project Layout

```
media-redact/
├── media_redact/
│   ├── detect/
│   │   ├── base.py         # Shared BBox types
│   │   ├── face/           # Face detection
│   │   └── osd/            # OSD detection
│   ├── mask/               # Masking effects
│   ├── pipeline/           # Image/video pipeline
│   ├── models/             # ONNX models (shipped in releases)
│   ├── tool/               # media-region annotator
│   └── cli.py              # CLI entry point
├── assets/
│   └── data/               # Optional sample inputs
├── tests/
├── pyproject.toml
├── uv.lock
└── docs/
    ├── README_CN.md        # Chinese documentation
    └── ROADMAP.md          # Roadmap
```

### Code Style (Ruff)

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
uv run ruff check media_redact tests      # lint
uv run ruff check --fix media_redact tests  # auto-fix
uv run ruff format media_redact tests     # format
```

### Adding Dependencies

```bash
uv add requests
```

---

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md).

- **v0.1** (current): Face detection + fixed-region OSD + image/video CLI
- **v0.2**: Python API, batch processing, GPU inference
- **v0.3**: OCR-based OSD text detection

## Acknowledgments

- [deface](https://github.com/ORB-HD/deface)

## License

TBD