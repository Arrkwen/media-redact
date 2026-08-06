# media-redact

> **English**: [README.md](../README.md)

图片与视频中的人脸及 OSD（屏幕叠加信息）打码工具。

| 原图 | 打码输出 |
| -------------- | ------------- |
| ![Original frame](assets/media/demo.jpg) | ![Redact output](assets/media/demo_redact.jpg) |

## 发版信息

详见 [ROADMAP.md](ROADMAP.md)。
- **v0.1**：人脸检测 + 固定区域 OSD + 图片/视频 CLI
- **v0.2**：Python API、批量处理
- **v0.3**（当前）：OCR 文字检测 OSD

## 功能

- **人脸打码**：ONNX 模型检测，支持 blur / mosaic / solid
- **固定 OSD 区域**：通过 `--osd-region` 打码用户指定的矩形/多边形（绝对像素坐标）
- **Band 区域 OSD**：通过 `--osd-band` 限定上下/左右 band，检测 band 内文字并全部打码
- **文字正则匹配 OSD**：PP-OCRv5 检测 + OCR，仅打码 `--osd-text` 正则匹配的识别文本
- **区域标注**：配套 Web 工具 `media-region`，在浏览器中画框/画线获取坐标与 band 比例
- **Python API 与 CLI 批处理**：支持目录批量处理并保留子目录结构（`-o` / `--output`、`--recursive`）


## 用户指南

完整安装、CLI 选项、OSD 格式、标注工具与 Python API 说明见 **[USER_GUIDE_CN.md](USER_GUIDE_CN.md)**。

## 开发指南

本地开发、测试与贡献说明见 **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)**（英文）。


## 致谢
感谢以下团队和个人的杰出工作：

- [deface](https://github.com/ORB-HD/deface)
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- [图片来源](https://www.zhihu.com/zvideo/1375093765468659712)（用于 README 展示；如侵权请联系我删除）

## License

待定
