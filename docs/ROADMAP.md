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
```

```
media-redact/
├── media_redact/           # 主包
│   ├── detect/
│   │   ├── base.py         # 公共 BBox
│   │   ├── face/           # 人脸检测
│   │   └── osd/            # OSD 检测
│   ├── mask/               # 打码（blur/mosaic/solid）
│   ├── pipeline/           # 图片/视频流水线
│   ├── models/             # ONNX 模型
│   ├── tool/               # media-region 区域标注
│   └── io/                 # 读写工具
├── assets/
│   └── data/               # 输入数据（可选）
└── tests/
```

## OSD 策略

### Phase 1 — 固定区域（已实现 v0.1）

通过坐标 ROI，适用于行车记录仪、监控摄像头等 OSD 位置固定的场景。

- 零推理开销，稳定无漏检

### Phase 2 — 文字检测（待实现）

- 模型：PaddleOCR det-only / DBNet ONNX
- 限域：仅上下 band 区域，减少误检
- 不做 OCR 识别，只要文字框

### Phase 3 — 智能过滤（待实现）

- 关键词/正则确认（时间戳格式等）
- 视频多帧时序稳定，减少闪烁

## 版本规划

### v0.1 — 基础可用（当前）

- [x] 项目结构与 `pyproject.toml`
- [x] YOLO ONNX 人脸检测（简化自 `src/face_detect`）
- [x] 打码：blur / mosaic / solid，椭圆/矩形 mask
- [x] 固定区域 OSD（YAML 配置）
- [x] 图片处理 CLI
- [x] 视频处理 CLI（保留音频选项）
- [x] 基础单元测试

### v0.2 — 易用性

- [x] 批量目录处理（Python API：`output_dir` + `recursive`）
- [x] Python API：`redact_image()` / `redact_video()`
- [x] 进度与日志完善（loguru + 批量文件进度条）

### v0.3 — OCR OSD

- [ ] PaddleOCR / DBNet 文字检测模块
- [ ] band 限域 + 规则过滤
- [ ] `--osd-text 支持文字正则过滤` CLI 选项

### v0.4 — 性能优化

- [ ] GPU 推理（onnxruntime CUDA EP）

- [ ] 视频人脸 tracking（跨帧复用 bbox）
- [ ] 多线程/异步 IO
- [ ] 分辨率自适应降采样推理

## CLI 用法

```bash
# 安装
pip install -e .

# 仅人脸打码
media-redact assets/data/input.mp4 --face -o output.mp4

# 仅 OSD
media-redact assets/data/image.jpg --osd \
  --osd-region 0,972;1920,972;1920,1080;0,1080 --mask-shape polygon

# 人脸 + OSD
media-redact assets/data/input.mp4 --face --osd \
  --osd-region 19,993,480,1079 \
  --osd-region 1344,993,1901,1079

```

## 依赖


| 包                             | 用途      |
| ----------------------------- | ------- |
| numpy, opencv-python-headless | 图像处理    |
| onnxruntime                   | ONNX 推理 |
| imageio[ffmpeg]               | 视频读写    |
| pyyaml                        | OSD 配置  |
| loguru                        | 日志      |
| tqdm                          | 进度条     |


## 变更记录


| 日期         | 版本   | 说明                               |
| ---------- | ---- | -------------------------------- |
| 2026-08-05 | v0.1 | 初始版本：人脸检测 + 固定区域 OSD + 图片/视频 CLI |


