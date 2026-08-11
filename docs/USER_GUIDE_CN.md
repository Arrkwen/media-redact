# 用户指南

> **English**: [USER_GUIDE.md](USER_GUIDE.md)

## 概览

`media-redact` 用于对图片与视频中的人脸及 OSD（屏幕叠加信息）打码。检测与打码解耦，每次运行可启用一种或多种模式。

| 模式 | 参数 | 适用场景 |
| ---- | ---- | -------- |
| 人脸打码 | `--face` | 自动检测并打码人脸 |
| 固定 OSD 区域 | `--osd-region` | 打码已知矩形/多边形（绝对像素坐标） |
| Band 区域 OSD | `--osd-band` | 打码 band 内检测到的全部文字 |
| 文字正则匹配 | `--osd-text` | OCR 后仅打码匹配正则的文本框 |

至少启用 `--face`、`--osd-region`、`--osd-band`、`--osd-text` 之一。

## 环境要求

- Python >= 3.10
- ffmpeg（视频处理必需；请单独安装并确保在 `PATH` 中）

## 安装

```bash
pip install media-redact

pip install "media-redact[gpu]"    # 如果有nvidia-gpu
```


| 命令 | 说明 |
| ---- | ---- |
| `media-redact` | 对图片/视频打码 |
| `media-region` | Web 区域标注；生成 `--osd-region` / `--osd-band` 参数 |

```bash
media-redact --version
media-region --help
```

人脸模型（`face_det.onnx`）与 OCR 资源默认缓存在 **`~/.media_redact/models/`**，**首次使用时自动下载**（不随 wheel 打包）。可通过环境变量 `MEDIA_REDACT_MODEL_ROOT` 覆盖路径。
## 快速上手

```bash
# 人脸
media-redact video.mp4 --face

# 固定 OSD 区域（1080p 底栏多边形）
media-redact image.jpg --osd-region 0,972;1920,972;1920,1080;0,1080

# Band OSD（底部 12% 内全部文字）
media-redact video.mp4 --osd-band bottom:0.12

# 文字正则（仅日期）
media-redact video.mp4 --osd-text '\d{4}-\d{2}-\d{2}'

# 组合多种模式
media-redact video.mp4 --face --osd-region 19,993,480,1079 --osd-band bottom:0.12

# 目录批处理
media-redact photos/ --face -r
media-redact input_dir/ --face -o output_dir/ -r
```

**默认输出**

| 输入 | 默认输出 |
| ---- | -------- |
| 单文件 / 文件列表 | `./output_redact/{原文件名}` |
| 目录 | `./output_redact/`（配合 `-r` 保留子目录结构） |

`-o` 指定输出**目录**（默认 `./output_redact`），输出文件名与输入相同。

## 打码模式

### 人脸（`--face`）

基于 ONNX 的人脸检测，可配置阈值与扩展系数：

```bash
media-redact video.mp4 --face --face-threshold 0.3 --mask-scale 1.3
```

### 固定 OSD 区域（`--osd-region`）

按**绝对像素坐标**打码用户指定区域。可重复指定；矩形与多边形可混用。

| 格式 | 示例（1080p） | 语法 |
| ---- | ------------- | ---- |
| 矩形 | `--osd-region 19,993,480,1079` | `x1,y1,x2,y2` |
| 多边形 | `--osd-region 0,972;1920,972;1920,1080;0,1080` | 顶点以 `;` 分隔 |

```bash
media-redact image.jpg \
  --osd-region "1138,430;1137,541;959,547;957,660;1257,673;1255,434" \
  --osd-region "27,613,276,679"
```

坐标与输入分辨率绑定。完全超出图像边界的区域会被**跳过**（不裁剪）。形状由 `--mask-shape` 控制（默认 `polygon`，亦支持 `ellipse`）。

### Band 区域 OSD（`--osd-band`）

整图文字检测后，保留中心点落在指定 band 内的框，**全部打码**（无 OCR）。

| Band | 示例 | 比例基准 |
| ---- | ---- | -------- |
| 上 / 下 | `top:0.15`、`bottom:0.12` | 图像高度 |
| 左 / 右 | `left:0.08`、`right:0.08` | 图像宽度 |

```bash
media-redact video.mp4 \
  --osd-band top:0.15 \
  --osd-band bottom:0.12
```

### 文字正则匹配（`--osd-text`）

整图 det →（可选 band 过滤）→ OCR → 正则匹配，**仅打码匹配框**。

```bash
# 整图
media-redact video.mp4 --osd-text '\d{4}-\d{2}-\d{2}'

# 限定 band 范围
media-redact video.mp4 \
  --osd-band bottom:0.15 \
  --osd-text '\d{4}-\d{2}-\d{2}' \
  --osd-text 'GPS[:：]\s*\d+'
```

多个 `--osd-text` 为正则 **OR** 匹配。

| 配置 | 流程 |
| ---- | ---- |
| 仅 `--osd-band` | 整图 det → band 过滤 → 打码全部框 |
| `--osd-text` | 整图 det →（可选 band 过滤）→ OCR → 正则 → 打码匹配框 |
| 仅 `--osd-region` | 固定坐标 → 直接打码（无文字检测） |

## CLI 参考

```
usage: media-redact [-h] [-o OUTPUT] [-r]
                    [--face] [--face-threshold FACE_THRESHOLD]
                    [--osd-region SPEC] [--osd-band SPEC] [--osd-text REGEX]
                    [--mask {blur,mosaic,solid,none}] [--mask-shape {ellipse,polygon}]
                    ...
                    input
```

| 选项 | 默认值 | 说明 |
| ---- | ------ | ---- |
| `input` | — | 图片/视频路径或目录 |
| `-o, --output` | 见上文 | 单文件时为输出文件；目录时为输出目录 |
| `-r, --recursive` | true | 递归处理子目录；可用 `--no-recursive` 关闭 |
| `--face` | false | 启用人脸打码 |
| `--face-threshold` | 0.3 | 人脸检测置信度阈值 |
| `--osd-region` | — | 固定 OSD 区域；可重复 |
| `--osd-band` | — | 文字检测 band；可重复 |
| `--osd-text` | — | OCR 正则；可重复（OR 匹配） |
| `--osd-text-threshold` | 0.3 | 文字概率图阈值 |
| `--osd-text-box-threshold` | 0.5 | 文字框分数阈值 |
| `--osd-text-rec-threshold` | 0.0 | OCR 最低置信度 |
| `--osd-text-model-size` | small | PP-OCRv6 文字 det/rec 模型尺寸：`tiny` / `small` / `medium` |
| `--mask` | mosaic | `blur` / `mosaic` / `solid` / `none` |
| `--mask-shape` | polygon | `ellipse` / `polygon` |
| `--mask-scale` | 1.3 | 人脸区域扩展（限制在图像内） |
| `--mosaic-size` | 20 | 马赛克块大小 |
| `--keep-audio` | false | 视频保留音轨 |
| `--disable-progress` | false | 关闭进度条 |
| `--device` | auto | ONNX 推理设备：`auto`（优先 CUDA）/ `cpu` / `cuda` |
| `--num-worker` | `min(4, CPU)` | 打码工作线程数；`>1` 启用读写流水线，`1` 为顺序处理 |
| `--log-level` | INFO | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

## 区域标注工具（`media-region`）

坐标未知时，可在浏览器中画框/画线并复制 CLI 或 API 片段（默认 `http://127.0.0.1:8765`）：

```bash
media-region                  # 启动标注
media-region frame.jpg        # 预加载图片或视频
media-region frame.jpg --port 9000
```

| 操作 | 说明 |
| ---- | ---- |
| 矩形 / `R` | 点击两角 → `--osd-region` |
| 多边形 / `P` | 点击顶点 → `--osd-region`；`N` 闭合 |
| Band 线 / `B` | 线段端点 → `--osd-band` 比例 |
| 撤销 / `U`、清空 / `C` | 撤销 / 清除全部 |
| Copy CLI / Copy API | 复制可直接运行的片段 |

## Python API

```python
redact_image(
    input,
    output=None,
    *,
    recursive=True,
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
    device="auto",
    num_worker=4,
    disable_progress=False,
)

redact_video(..., keep_audio=False)  # 其余参数与 redact_image 相同
```

```python
from media_redact import redact_image, redact_video
# from media_redact.log import setup_logging
# setup_logging("INFO")  # DEBUG / INFO / WARNING / ERROR


# 单文件（默认输出 ./output_redact/photo.jpg）
redact_image("photo.jpg", face=True)

# 指定输出目录
redact_image("photo.jpg", output="out/", face=True)

# 目录批处理（保留目录结构）
redact_image(
    "input_dir/",
    output="output_dir/",
    recursive=True,
    face=True,
    face_threshold=0.3,
)

# 多文件
redact_image(
    ["a.jpg", "b.jpg"],
    output="output_dir/",
    osd_regions=["0,972;1920,972;1920,1080;0,1080"],
)

# 视频
redact_video(
    "input_videos/",
    output="output_videos/",
    recursive=True,
    face=True,
    osd_bands=["bottom:0.12"],
    osd_text=[r"\d{4}-\d{2}-\d{2}"],
    keep_audio=True,
)
```

CLI 与 Python API 均使用 ``output`` 指定输出目录；省略时默认为 ``./output_redact/``。

## 延伸阅读

- [Developer Guide](DEVELOPER_GUIDE.md) — 项目结构、打码流程图、测试与展示图生成
