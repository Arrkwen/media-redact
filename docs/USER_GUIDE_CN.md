# 用户指南

> **English**: [USER_GUIDE.md](USER_GUIDE.md)

## 环境要求

- Python >= 3.10
- ffmpeg（视频处理必需；请单独安装并确保在 `PATH` 中）

## 安装

```bash
pip install media-redact
```

若尚未发布到 PyPI，可从源码安装：

```bash
pip install /path/to/media-redact          # 本地目录
# 或
pip install git+https://example.com/media-redact.git
```

安装后提供两个命令：


| 命令           | 说明                                                         |
| -------------- | ------------------------------------------------------------ |
| `media-redact` | 对图片/视频打码                                              |
| `media-region` | Web 区域标注；生成 `--osd-region` / `--osd-band` 参数片段   |


验证安装：

```bash
media-redact --version
media-region --help
```

打码时需显式启用 `--face`（人脸）和/或 OSD 相关选项。人脸模型已随包内置（`media_redact/models/face_det.onnx`），无需额外配置。

## 基本用法

```bash
# 仅人脸打码
media-redact video.mp4 --face

# 仅固定 OSD 区域（1920×1080 底栏多边形）
media-redact image.jpg \
  --osd-region 0,972;1920,972;1920,1080;0,1080

# 人脸 + 固定 OSD（1080p 示例：左下/右下时间戳区域）
media-redact video.mp4 \
  --face \
  --osd-region 19,993,480,1079 \
  --osd-region 1344,993,1901,1079

# 目录批处理（图片与视频）；默认输出：./{dirname}_redacted/
media-redact photos/ --face --recursive

# 指定输出目录（保留子目录结构）
media-redact input_dir/ --face -o output_dir/ --recursive
```

**单文件**默认输出：当前工作目录下的 `{filename}_redacted.{ext}`。

**目录**默认输出：当前工作目录下的 `{dirname}_redacted/`。

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

## CLI 选项

```
usage: media-redact [-h] [-o OUTPUT] [-r]
                    [--face] [--face-threshold FACE_THRESHOLD]
                    [--osd-region SPEC] [--osd-band SPEC] [--osd-text REGEX]
                    ...
                    input
```


| 选项                 | 默认值    | 说明                                                         |
| -------------------- | --------- | ------------------------------------------------------------ |
| `input`              | —         | 输入图片/视频路径 **或目录**                                 |
| `-o, --output`       | 见下文    | 单文件时为输出**文件**；目录输入时为输出**目录**             |
| `-r, --recursive`    | false     | 递归处理子目录中的文件                                       |
| `--face`             | false     | 启用人脸打码（内置 `media_redact/models/face_det.onnx`）   |
| `--face-threshold`   | 0.3       | 人脸检测置信度阈值                                           |
| `--osd-region`       | —         | 固定 OSD 区域（绝对像素坐标）；可重复指定                    |
| `--osd-band`         | —         | 文字检测 band（`top:0.15`、`bottom:0.12` 等）；可重复指定；用于过滤检测框 |
| `--osd-text`         | —         | OCR 正则过滤；可重复指定（OR 匹配）                          |
| `--mask`             | mosaic    | 打码模式：blur / mosaic / solid / none                       |
| `--mask-shape`       | polygon   | 区域形状：ellipse / polygon                                  |
| `--mask-scale`       | 1.3       | 人脸区域扩展系数（限制在图像边界内）                         |
| `--mosaic-size`      | 20        | 马赛克块大小                                                 |
| `--keep-audio`       | false     | 视频保留原始音轨                                             |
| `--disable-progress` | false     | 关闭帧进度与批处理文件进度条                                 |
| `--log-level`        | INFO      | 日志级别（DEBUG / INFO / WARNING / ERROR）                   |


## OSD 区域格式

`--osd-region` 使用**绝对像素坐标**。通过重复该参数指定多个区域：


| 格式   | 示例（1080p）                                  | 说明              |
| ------ | ---------------------------------------------- | ----------------- |
| 矩形   | `--osd-region 19,993,480,1079`                 | `x1,y1,x2,y2`（像素） |
| 多边形 | `--osd-region 0,972;1920,972;1920,1080;0,1080` | 顶点以 `;` 分隔   |


同一命令中可**混合**矩形与多边形——在 CLI 上重复 `--osd-region`，或在 Python 中传入 `osd_regions` 列表：

```bash
# CLI：一个多边形 + 一个矩形
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
        "1138,430;1137,541;959,547;957,660;1257,673;1255,434",  # 多边形
        "27,613,276,679",                                          # 矩形
    ],
)
```

> **说明**：坐标与输入图片/视频分辨率绑定。完全超出图像边界的区域会被**跳过**（不会裁剪）。

区域形状由 `--mask-shape` 控制（默认 `polygon`；亦支持 `ellipse`）。

## OCR 文字 OSD（`--osd-band` / `--osd-text`）

基于 PP-OCRv5 的文字检测/识别，无需手动坐标。请先下载 OCR 模型：

```bash
python scripts/download_ocr_models.py
```

**`--osd-band`** 与 **`--osd-text`** 均支持**重复指定**（与 `--osd-region` 相同）——可传入多个 band 或正则：


| 选项         | 格式                                                    | 说明                                                         |
| ------------ | ------------------------------------------------------- | ------------------------------------------------------------ |
| `--osd-band` | `top:0.15` / `bottom:0.12` / `left:0.08` / `right:0.08` | 上下比例相对图像高度；左右相对宽度；可重复指定               |
| `--osd-text` | Python 正则                                             | 启用 OCR；仅打码匹配框；可重复指定（**OR** 匹配）            |


```bash
# 在多个 band 内打码全部文字（仅检测，无 OCR）
media-redact video.mp4 \
  --osd-band top:0.15 \
  --osd-band bottom:0.12 \
  --osd-band left:0.08

# 多个正则（日期或速度）
media-redact video.mp4 \
  --osd-text '\d{4}-\d{2}-\d{2}' \
  --osd-text '\d+\s*km/h'

# band + 多个正则
media-redact video.mp4 \
  --osd-band bottom:0.15 \
  --osd-text '\d{4}-\d{2}-\d{2}' \
  --osd-text 'GPS[:：]\s*\d+'
```

```python
# Python API：传入 band / 正则列表
redact_video(
    "video.mp4",
    osd_bands=["top:0.15", "bottom:0.12", "right:0.1"],
    osd_text=[r"\d{4}-\d{2}-\d{2}", r"\d+\s*km/h"],
)
```


| 模式              | 行为                                                         |
| ----------------- | ------------------------------------------------------------ |
| 仅 `--osd-band`   | 整图 det → band 过滤 → **打码全部框**（无 OCR）              |
| `--osd-text`      | 整图 det →（可选 band 过滤）→ OCR → 正则 → **打码匹配框** |
| 仅 `--osd-region` | 固定坐标 → **直接打码区域**（无文字检测）                    |


## 区域标注工具（`media-region`）

坐标未知时，可用 Web 界面绘制矩形、多边形或 band 线，并复制 CLI 或 Python API 片段（默认 `http://127.0.0.1:8765`）：

```bash
# 启动标注工具（在页面中上传图片/视频或输入流 URL）
media-region

# 预加载图片或视频
media-region frame.jpg

# 自定义端口（远程主机可配合 SSH 端口转发）
media-region frame.jpg --port 9000

# 调试 RTSP/流连接
media-region --log-level DEBUG
```


| 操作                 | 说明                                                         |
| -------------------- | ------------------------------------------------------------ |
| 上传图片             | 在浏览器中直接加载                                           |
| 上传视频             | 提取首帧；优先浏览器端，其次分块上传或 OpenCV 回退          |
| 流 URL               | 提取首帧；优先浏览器端，其次 OpenCV 后端回退                 |
| 矩形 / `R`           | 点击两角，生成固定 `--osd-region`                            |
| 多边形 / `P`         | 点击顶点，生成固定 `--osd-region`                            |
| Band 线 / `B`        | 点击线段端点，生成 `--osd-band` 比例                         |
| 完成多边形 / `N`     | 闭合当前多边形（≥3 个点）                                    |
| 撤销 / `U`           | 撤销上一步                                                   |
| 清空 / `C`           | 清除全部区域（避免 Ctrl+C——会触发清空）                      |
| Copy CLI             | 复制 `media-redact` 命令片段                                 |
| Copy API             | 复制 Python `redact_image()` 调用片段                        |
| Download coords.txt  | 导出 CLI 与 API 片段                                         |


将复制的参数用于 `media-redact` 即可。

## Python API

也可在 Python 中调用 `redact_image()` / `redact_video()`。输入可以是单文件、多文件或目录（可选递归遍历）。批处理时通过 `output_dir` 指定输出根目录——**保留相对子目录结构**，每个文件名追加 `_redacted` 后缀。

```python
from media_redact import redact_image, redact_video

# 单张图片
redact_image("photo.jpg", face=True)

# 指定输出路径
redact_image("photo.jpg", "out.jpg", face=True)

# 目录批处理（递归），保留子目录
redact_image(
    "input_dir/",
    output_dir="output_dir/",
    recursive=True,
    face=True,
)

# 多个文件
redact_image(
    ["a.jpg", "b.jpg"],
    output_dir="output_dir/",
    osd_regions=["0,972;1920,972;1920,1080;0,1080"],
)

# 视频用法相同
redact_video(
    "input_videos/",
    output_dir="output_videos/",
    recursive=True,
    face=True,
    keep_audio=True,
)
```
