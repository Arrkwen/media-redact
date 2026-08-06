# Developer Guide

For contributors running tests and developing locally. [uv](https://docs.astral.sh/uv/) is recommended for dependency and virtualenv management.

## Requirements

- Python >= 3.10
- [uv](https://docs.astral.sh/uv/) (recommended)
- ffmpeg

## Clone and Sync

```bash
git clone <repo-url> media-redact
cd media-redact
uv sync --group dev
```

This will:

- Create a project virtual environment (`.venv/`)
- Install dependencies from `uv.lock`
- Install the package in editable mode

## Resources

Runtime models are cached under **`~/.media_redact/models/`** by default (override with `MEDIA_REDACT_MODEL_ROOT`). They are **not shipped in the wheel**; missing assets are downloaded on first use:

| Asset | Source |
| ----- | ------ |
| `face_det.onnx` | GitHub repo (`assets/models/face_det.onnx`) |
| OCR (`text_det.onnx`, `text_rec.onnx`, `ppocrv6_dict.txt`) | ModelScope RapidOCR PP-OCRv6 small |

`assets/models/face_det.onnx` is tracked in git as the upstream source. OCR files are fetched automatically into the user cache directory.

Optional test data lives under `assets/data/` at the repo root:

```bash
assets/
├── models/
│   └── face_det.onnx      # Face model source (in git)
├── media/                 # README demo images
└── data/                  # Sample inputs (optional, not packaged)

~/.media_redact/models/    # Default runtime cache (auto-created)
```

Prefetch all models:

```bash
python scripts/download_models.py
```

## Run and Test

```bash
# Redact (use uv run in development)
uv run media-redact assets/data/video.mp4 \
  --face \
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

Regenerate README demo images (requires OCR models and sample data under `assets/media/`):

```bash
python scripts/generate_readme_demos.py
```

Outputs are written to `assets/media/demo_preview.jpg` and `assets/media/demo_redact.jpg` (both scaled to the same width for README comparison).

After activating the virtual environment:

```bash
source .venv/bin/activate
media-redact --help
media-region --help
pytest
```

## Common uv Commands


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


## Project Layout

```
media-redact/
├── media_redact/
│   ├── detect/
│   │   ├── base.py         # Shared BBox types
│   │   ├── face/           # Face detection
│   │   └── osd/            # OSD detection
│   ├── mask/               # Masking effects
│   ├── pipeline/           # Image/video pipeline
│   ├── model/              # Model download helpers (not runtime cache)
│   ├── tool/               # media-region annotator
│   └── cli.py              # CLI entry point
├── assets/
│   └── data/               # Optional sample inputs
├── tests/
├── pyproject.toml
├── uv.lock
└── docs/
    ├── USER_GUIDE.md       # User guide
    ├── DEVELOPER_GUIDE.md  # This file
    ├── README_CN.md        # Chinese README (overview)
    ├── images/             # (optional) legacy README assets
    └── ROADMAP.md          # Roadmap
```

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

## Code Style (Ruff)

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
uv run ruff check media_redact tests      # lint
uv run ruff check --fix media_redact tests  # auto-fix
uv run ruff format media_redact tests     # format
```

## Adding Dependencies

```bash
uv add requests
```

## Publishing to PyPI

Uses the same **GitHub Actions + PyPI Trusted Publishing** flow (workflow name: `media-redact-publisher`).

**One-time setup (PyPI + GitHub):**

1. Open **account-level** Trusted Publishing (not inside an existing project):
  [https://pypi.org/manage/account/publishing/](https://pypi.org/manage/account/publishing/)
2. Use **Create a new pending publisher** and fill in:
  - **PyPI project name**: `media-redact` (must match `pyproject.toml` `name` exactly)
  - **Owner / Repository**: your GitHub repo
  - **Workflow name**: `publish.yml`
  - **Environment name**: `media-redact-publisher`

**Release steps:**

1. Bump `version` in `pyproject.toml`
2. Commit and push to `main`
3. Create a **Published** GitHub Release with a matching tag (e.g. `v0.2.0` or `0.2.0`)
4. `[.github/workflows/publish.yml](../.github/workflows/publish.yml)` builds and uploads to PyPI

You can also run **Actions → media-redact-publisher → Run workflow** manually.

Verify locally:

```bash
uv build
ls dist/
```

