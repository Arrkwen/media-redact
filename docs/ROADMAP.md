# media-redact 项目 Roadmap

> 图片/视频中的人脸与 OSD 信息打码工具包。本文档指导后续开发与迭代。

## 目标

构建独立 Python 包 `media_redact`，统一处理：


| 能力     | 输入      | 输出         |
| ------ | ------- | ---------- |
| 人脸打码   | 图片 / 视频 | 打码后的媒体文件   |
| OSD 打码 | 图片 / 视频 | 同上（可与人脸叠加） |


设计原则：

1. **检测与打码解耦** — 检测器只输出 bbox，打码器统一消费
2. **分阶段交付** — 先做人脸 + 固定区域 OSD，再扩展 OCR

## 架构

```
输入帧 → [人脸检测] + [OSD 检测] → 合并 bbox → 统一打码 → 输出
                      ├─ 固定区域 (RegionOSDDetector)
                      └─ 文字检测 (TextOSDDetector, PP-OCRv5_mobile_det)
```

```
media-redact/
├── media_redact/           # 主包
│   ├── detect/
│   │   ├── base.py         # 公共 BBox
│   │   ├── face/           # 人脸检测
│   │   └── osd/            # OSD 检测
│   │       ├── region.py   # 固定区域
│   │       ├── text_detector.py
│   │       ├── db_postprocess.py
│   │       ├── bands.py
│   │       └── composite.py
│   ├── mask/               # 打码（blur/mosaic/solid）
│   ├── pipeline/           # 图片/视频流水线
│   ├── model/              # ONNX 模型（按需下载，不打进 wheel）
│   │   ├── face_det.onnx
│   │   └── text_det.onnx   # PP-OCRv5_mobile_det
│   ├── tool/               # media-region 区域标注
│   └── io/                 # 读写工具
├── assets/
│   └── data/               # 输入数据（可选）
└── tests/
```

## OSD 策略

### Phase 1 — 固定区域（v0.1）

通过坐标 ROI，适用于行车记录仪、监控摄像头等 OSD 位置固定的场景。

- 零推理开销，稳定无漏检

### Phase 2 — 文字检测（v0.3）

- 模型：**PP-OCRv5_mobile_det** ONNX（`text_det.onnx`）
- 限域：通过 `--osd-band` 或配合 `--osd-region` 过滤检测框

### Phase 3 — 识别 + 正则过滤（v0.3）

- 模型：**PP-OCRv5_mobile_rec** ONNX（`text_rec.onnx`）+ `ppocrv5_dict.txt`
- 流程：full-image det → (band filter if set) → OCR → text regex
- [ ] 视频多帧时序稳定，减少闪烁

## 版本规划

### v0.1 — 基础可用

- [x] 项目结构与 `pyproject.toml`
- [x] YOLO ONNX 人脸检测
- [x] 打码：blur / mosaic / solid，椭圆/多边形 mask
- [x] 固定区域 OSD
- [x] 图片/视频 CLI
- [x] 基础单元测试

### v0.2 — 易用性

- [x] 批量目录处理（CLI：`-o` 目录 + `--recursive`；API：`output_dir` + `recursive`）
- [x] Python API：`redact_image()` / `redact_video()`
- [x] 进度与日志完善（loguru + 批量文件进度条）

### v0.3 — OCR OSD

- [x] PP-OCRv5_mobile_det 文字检测（`TextOSDDetector`）
- [x] PP-OCRv5_mobile_rec 文字识别 + `--osd-text` 正则过滤
- [x] band 限域 + 几何规则过滤
- [x] CLI/API：`--osd-text`、`--osd-band`
- [ ] 视频时序稳定

> **依赖说明**：PP-OCRv5 ONNX（IR v10）需要 **onnxruntime>=1.18**（容器内开发环境通常满足）。

### v0.4 — 性能优化

- [ ] GPU 推理（onnxruntime CUDA EP）
- [ ] 视频人脸 tracking（跨帧复用 bbox）
- [ ] 多线程/异步 IO
- [ ] 分辨率自适应降采样推理
- [ ] 文字检测隔帧推理 + 时序插值

## CLI 用法

```bash
# 安装
pip install -e .

# 预下载模型（也可在首次打码时自动下载）
python scripts/download_models.py

# 仅人脸打码
media-redact assets/data/input.mp4 --face -o output.mp4

# 固定区域 OSD
media-redact assets/data/image.jpg \
  --osd-region 0,972;1920,972;1920,1080;0,1080 --mask-shape polygon

# 预下载 OCR 模型与字典（首次 --osd-text / --osd-band 时也会自动下载）
python scripts/download_models.py --ocr

# band 内文字检测（全部打码）
media-redact assets/data/image.jpg --osd-band bottom:0.12

# band + 正则 OCR（仅匹配框打码）
media-redact assets/data/image.jpg \
  --osd-band bottom:0.15 \
  --osd-text '\d{4}-\d{2}-\d{2}'

# 仅正则 OCR（默认上下 band）
media-redact assets/data/image.jpg \
  --osd-text '\d{4}-\d{2}-\d{2}' \
  --osd-text '\d+\s*km/h'

# 固定区域 + 文字 OCR
media-redact assets/data/input.mp4 \
  --osd-region 19,993,480,1079 \
  --osd-text '\d{4}-\d{2}-\d{2}' \
  --osd-band bottom:0.15

# 人脸 + OCR OSD
media-redact assets/data/input.mp4 --face \
  --osd-text '\d{4}-\d{2}-\d{2}'
```

## 依赖


| 包                             | 用途      |
| ----------------------------- | ------- |
| numpy, opencv-python-headless | 图像处理    |
| onnxruntime                   | ONNX 推理 |
| pyclipper                     | DB 后处理 unclip |
| imageio[ffmpeg]               | 视频读写    |
| loguru                        | 日志      |
| tqdm                          | 进度条     |


## 变更记录


| 日期         | 版本   | 说明                               |
| ---------- | ---- | -------------------------------- |
| 2026-08-05 | v0.1 | 初始版本：人脸检测 + 固定区域 OSD + 图片/视频 CLI |
| 2026-08-06 | v0.3 | PP-OCRv5_mobile_det 文字 OSD（Phase 2） |
