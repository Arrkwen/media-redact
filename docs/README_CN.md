# media-redact

> **English**: [README.md](../README.md)

图片与视频中的人脸及 OSD（屏幕叠加信息）打码工具。

支持对图片、视频进行人脸检测打码，以及基于固定区域的 OSD 信息打码（时间戳、GPS、设备 ID 等）。检测与打码解耦，可按需单独启用人脸或 OSD 处理。

## 功能

- **人脸打码**：ONNX 模型检测，支持 blur / mosaic / solid
- **OSD 打码**：CLI 指定固定区域（绝对像素坐标）
- **区域标注**：配套 Web 工具 `media-region`，在浏览器中画框获取坐标

---

## 用户指南

### 环境要求

- Python >= 3.10
- ffmpeg（处理视频时需要，请自行安装并确保在 `PATH` 中）

### 安装

```bash
pip install media-redact
```

若包尚未发布到 PyPI，可从源码安装：

```bash
pip install /path/to/media-redact          # 本地目录
# 或
pip install git+https://example.com/media-redact.git
```

安装完成后会提供两个命令：


| 命令             | 说明                            |
| -------------- | ----------------------------- |
| `media-redact` | 对图片/视频打码                      |
| `media-region` | Web 区域标注，生成 `--osd-region` 坐标 |


验证安装：

```bash
media-redact --version
media-region --help
```

打码时需显式指定 `--face`（人脸）和/或 `--osd`（固定区域）；人脸模型随安装包提供（`media_redact/models/face_det.onnx`），无需额外配置。

### 基本用法

```bash
# 仅人脸打码
media-redact video.mp4 --face

# 仅 OSD 打码（底部栏多边形，1920x1080）
media-redact image.jpg \
  --osd \
  --osd-region 0,972;1920,972;1920,1080;0,1080 

# 人脸 + OSD 打码（1080p 示例：左下角时间戳区域）
media-redact video.mp4 \
  --face \
  --osd \
  --osd-region 19,993,480,1079 \
  --osd-region 1344,993,1901,1079

# 指定输出路径
media-redact video.mp4 --face -o output.mp4

# 视频保留原音频
media-redact video.mp4 --face --keep-audio
```

默认输出文件为当前目录下的 `{文件名}_redacted.{扩展名}`。

### CLI 参数

```
usage: media-redact [-h] [-o OUTPUT]
                    [--face] [--face-threshold FACE_THRESHOLD]
                    [--osd] [--osd-region SPEC]
                    [--mask {blur,mosaic,solid,none}]
                    [--mask-shape {ellipse,polygon}]
                    [--mask-scale MASK_SCALE] [--mosaic-size MOSAIC_SIZE]
                    [--keep-audio] [--disable-progress] [--version]
                    input
```


| 参数                 | 默认值     | 说明                                               |
| ------------------ | ------- | ------------------------------------------------ |
| `input`            | —       | 输入图片或视频路径                                        |
| `-o, --output`     | 见说明     | 输出路径；默认 `{stem}_redacted{ext}`                   |
| `--face`           | false   | 启用人脸打码（使用内置 `media_redact/models/face_det.onnx`） |
| `--face-threshold` | 0.3     | 人脸检测置信度阈值                                        |
| `--osd`            | false   | 启用 OSD 固定区域打码（需配合 `--osd-region`）                |
| `--osd-region`     | —       | OSD 区域（绝对像素坐标，可重复指定）                             |
| `--mask`           | mosaic  | 打码方式（blur / mosaic / solid / none）               |
| `--mask-shape`     | polygon | 打码区域形状（ellipse / polygon）                        |
| `--mask-scale`     | 1.3     | 人脸区域扩展比例                                         |
| `--mosaic-size`    | 20      | 马赛克块大小                                           |
| `--keep-audio`     | false   | 视频保留原音频                                          |


### OSD 区域参数

`--osd-region` 使用**绝对像素坐标**，可多次指定多个区域：


| 格式  | 示例（1080p）                                      | 说明                |
| --- | ---------------------------------------------- | ----------------- |
| 矩形  | `--osd-region 19,993,480,1079`                 | `x1,y1,x2,y2`（像素） |
| 多边形 | `--osd-region 0,972;1920,972;1920,1080;0,1080` | 点用 `;` 分隔         |


> **注意**：坐标与输入视频/图片分辨率绑定。换分辨率需重新指定区域。

打码形状由 `--mask-shape` 控制，默认为 `polygon`（多边形轮廓），也可选 `ellipse`（椭圆）。

### 区域标注工具（`media-region`）

不确定坐标时，可用 Web 界面在浏览器中画框/多边形，复制 `--osd-region` 参数（默认 `http://127.0.0.1:8765`）：

```bash
# 启动标注服务（页内可上传图片/视频或输入流地址）
media-region

# 预加载图片或视频
media-region frame.jpg

# 指定端口（远程环境可配合 SSH 端口转发）
media-region frame.jpg --port 9000

# 排查 RTSP/流连接问题
media-region --log-level DEBUG
```


| 操作            | 功能                              |
| ------------- | ------------------------------- |
| 上传图片          | 前端直接加载                          |
| 上传视频          | 自动取第一帧；优先前端，失败则分块上传或由 OpenCV 取帧 |
| 视频流 URL       | 自动取第一帧；优先前端，失败则后端 OpenCV 取帧     |
| 矩形模式 / `R`    | 点击两个对角点画框                       |
| 多边形模式 / `P`   | 点击描点                            |
| 完成多边形 / `N`   | 结束当前多边形（≥3 点）                   |
| 撤销 / `U`      | 撤销                              |
| 清空 / `C`      | 清空全部                            |
| 复制命令          | 复制 `--osd-region` 片段            |
| 下载 coords.txt | 导出坐标文件                          |


标注完成后，将复制的参数与 `--osd` 一起用于 `media-redact` 即可。

---

## 开发者指南

面向参与本项目开发、调试与测试的开发者。推荐使用 [uv](https://docs.astral.sh/uv/) 管理依赖与虚拟环境。

### 环境要求

- Python >= 3.10
- [uv](https://docs.astral.sh/uv/)（推荐）
- ffmpeg

### 克隆与同步环境

```bash
git clone <repo-url> media-redact
cd media-redact
uv sync --group dev
```

该命令会：

- 创建项目虚拟环境（`.venv/`）
- 根据 `uv.lock` 安装依赖
- 以可编辑模式安装本包

### 资源目录

`media_redact/models/face_det.onnx` 为人脸检测模型，**发版时需打包进安装包**。可选测试数据放在仓库根目录 `assets/data/`：

```bash
media_redact/
└── models/face_det.onnx   # 人脸模型（发版包内置）

assets/
└── data/                  # 输入图片/视频（可选，不打包）
```

### 运行与测试

```bash
# 打码（开发环境用 uv run 调用 CLI）
uv run media-redact assets/data/video.mp4 \
  --face \
  --osd \
  --osd-region 19,993,480,1079 \
  --mask-shape polygon

# 区域标注
uv run media-region assets/data/frame.jpg

# 运行测试
uv run pytest
```

激活虚拟环境后也可直接使用命令：

```bash
source .venv/bin/activate
media-redact --help
media-region --help
pytest
```

### 常用 uv 命令


| 命令                        | 说明           |
| ------------------------- | ------------ |
| `uv sync`                 | 同步生产依赖并安装本包  |
| `uv sync --group dev`     | 同步生产 + 开发依赖  |
| `uv run media-redact ...` | 在项目环境中运行 CLI |
| `uv run pytest`           | 运行测试         |
| `uv add <package>`        | 添加依赖         |
| `uv lock`                 | 更新锁文件        |


### 项目结构

```
media-redact/
├── media_redact/
│   ├── detect/
│   │   ├── base.py         # 公共 BBox
│   │   ├── face/           # 人脸检测
│   │   └── osd/            # OSD 检测
│   ├── mask/               # 打码效果
│   ├── pipeline/           # 图片/视频流水线
│   ├── models/             # ONNX 模型（发版打包）
│   ├── tool/               # media-region 区域标注工具
│   └── cli.py              # 命令行入口
├── assets/
│   └── data/               # 输入数据（可选）
├── tests/
├── pyproject.toml
├── uv.lock
└── docs/
    ├── README_CN.md        # 中文文档
    └── ROADMAP.md          # 版本规划与开发路线
```

### 添加依赖

```bash
uv add requests
uv add --group dev ruff
```

---

## 路线图

详见 [docs/ROADMAP.md](./ROADMAP.md)。

- **v0.1**（当前）：人脸检测 + 固定区域 OSD + 图片/视频 CLI
- **v0.2**：Python API、批量处理、GPU 推理
- **v0.3**：OCR 文字检测 OSD

## 致谢

- [deface](https://github.com/ORB-HD/deface)

## License

待定