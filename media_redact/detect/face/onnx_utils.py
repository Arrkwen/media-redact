"""YOLO ONNX 人脸检测推理工具。"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def parse_model_input_size(model_path: str | Path, session) -> tuple[int, int]:
    """
    从 ONNX 模型读取输入尺寸 (width, height)。

    优先读取 session 输入 shape；若为动态维度，则解析 ONNX 图定义。
    """
    shape = session.get_inputs()[0].shape
    if len(shape) == 4:
        height = _dim_to_int(shape[2])
        width = _dim_to_int(shape[3])
        if height and width:
            return width, height

    import onnx

    model = onnx.load(str(model_path))
    if not model.graph.input:
        raise ValueError(f"Cannot determine input size from model: {model_path}")

    dims = model.graph.input[0].type.tensor_type.shape.dim
    if len(dims) != 4:
        raise ValueError(
            f"Expected NCHW input, got {len(dims)} dims in {model_path}"
        )

    height = _dim_to_int(dims[2].dim_value or dims[2].dim_param)
    width = _dim_to_int(dims[3].dim_value or dims[3].dim_param)
    if height and width:
        return width, height

    raise ValueError(
        f"Model input size is dynamic and cannot be inferred: {model_path}. "
        "Please use an ONNX model with fixed H/W dimensions."
    )


def _dim_to_int(dim) -> int | None:
    if isinstance(dim, int) and dim > 0:
        return dim
    if isinstance(dim, str) and dim.isdigit():
        return int(dim)
    return None


def letterbox(
    im: np.ndarray,
    new_shape: tuple[int, int] = (640, 640),
    color: tuple[int, int, int] = (0, 0, 0),
    scaleup: bool = False,
):
    shape = im.shape[:2]
    ratio = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    if not scaleup:
        ratio = min(ratio, 1.0)

    new_unpad = (int(round(shape[1] * ratio)), int(round(shape[0] * ratio)))
    im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    padded = np.full((new_shape[0], new_shape[1], 3), color, dtype=np.uint8)
    padded[: new_unpad[1], : new_unpad[0]] = im
    return padded, (ratio, ratio), (0, 0)


def preprocess_bgr(
    ori_img: np.ndarray,
    input_width: int,
    input_height: int,
    *,
    image_format: str = "rgb",
):
    if ori_img is None or ori_img.size == 0:
        raise ValueError("Input image is empty")

    fmt = image_format.lower()
    if fmt not in {"bgr", "rgb", "gray"}:
        raise ValueError(f"Unsupported image_format: {image_format}")

    res_img, ratio, (dw, dh) = letterbox(
        ori_img, (input_height, input_width), scaleup=False
    )

    if fmt == "rgb":
        model_input = cv2.cvtColor(res_img, cv2.COLOR_BGR2RGB)
    elif fmt == "gray":
        model_input = cv2.cvtColor(res_img, cv2.COLOR_BGR2GRAY)[:, :, np.newaxis]
    else:
        model_input = res_img

    model_input = model_input.transpose((2, 0, 1))
    model_input = np.ascontiguousarray(model_input, dtype=np.float32) / 255.0
    model_input = np.expand_dims(model_input, axis=0)
    return model_input, ratio, dw, dh


def postprocess_detection_outputs(
    session_like_outputs: list[np.ndarray],
    ratio,
    dw: float,
    dh: float,
    confidence_thres: float,
    iou_thres: float,
) -> list[dict]:
    outputs = np.transpose(np.squeeze(session_like_outputs[0]))

    boxes: list[list[int]] = []
    scores: list[float] = []
    class_ids: list[int] = []

    x_factor = 1 / ratio[1] if ratio and ratio[1] != 0.0 else 1.0
    y_factor = 1 / ratio[0] if ratio and ratio[0] != 0.0 else 1.0

    for row in outputs:
        classes_scores = row[4:]
        max_score = float(np.amax(classes_scores))
        class_id = int(np.argmax(classes_scores))
        if max_score < confidence_thres or class_id == 0:
            continue

        x, y, w, h = row[:4]
        left = int(max((x - w * 0.5 - dw), 0) * x_factor)
        top = int(max((y - h * 0.5 - dh), 0) * y_factor)
        width = int(w * x_factor)
        height = int(h * y_factor)

        boxes.append([left, top, width, height])
        scores.append(max_score)
        class_ids.append(class_id)

    if not boxes:
        return []

    nms_indices = cv2.dnn.NMSBoxes(
        boxes, scores, confidence_thres, iou_thres, eta=0.5, top_k=300
    )

    detections: list[dict] = []
    for idx in nms_indices:
        i = int(np.array(idx).reshape(-1)[0])
        x1, y1, w, h = boxes[i]
        detections.append(
            {
                "bbox": [int(x1), int(y1), int(x1 + w), int(y1 + h)],
                "score": float(scores[i]),
                "label": int(class_ids[i]),
            }
        )
    return detections


def postprocess_multiscale_outputs(
    session_like_outputs: list[np.ndarray],
    ratio,
    dw: float,
    dh: float,
    confidence_thres: float,
    iou_thres: float,
    strides: tuple[int, ...] = (8, 16, 32),
) -> list[dict]:
    pad_w, pad_h = dw, dh
    x_factor = 1 / ratio[1] if ratio and ratio[1] != 0.0 else 1.0
    y_factor = 1 / ratio[0] if ratio and ratio[0] != 0.0 else 1.0

    boxes: list[list[int]] = []
    scores: list[float] = []
    class_ids: list[int] = []

    num_levels = len(session_like_outputs) // 2
    for level in range(num_levels):
        cls_out = np.squeeze(np.asarray(session_like_outputs[2 * level]), axis=0)
        reg_out = np.squeeze(np.asarray(session_like_outputs[2 * level + 1]), axis=0)
        stride = strides[level] if level < len(strides) else strides[-1]

        _, h, w_grid = cls_out.shape
        gy, gx = np.meshgrid(np.arange(h), np.arange(w_grid), indexing="ij")
        anchor_x = (gx + 0.5) * stride
        anchor_y = (gy + 0.5) * stride

        cx = (anchor_x + reg_out[0] * stride).reshape(-1)
        cy = (anchor_y + reg_out[1] * stride).reshape(-1)
        bw = (np.exp(reg_out[2]) * stride).reshape(-1)
        bh = (np.exp(reg_out[3]) * stride).reshape(-1)

        cls_flat = cls_out.reshape(cls_out.shape[0], -1)
        max_scores = cls_flat.max(axis=0)
        max_class_ids = cls_flat.argmax(axis=0)

        for idx in np.flatnonzero(max_scores >= confidence_thres):
            if int(max_class_ids[idx]) == 0:
                continue
            x, y, w, hgt = cx[idx], cy[idx], bw[idx], bh[idx]
            left = int(max((x - w * 0.5 - pad_w), 0) * x_factor)
            top = int(max((y - hgt * 0.5 - pad_h), 0) * y_factor)
            width = int(w * x_factor)
            height = int(hgt * y_factor)

            boxes.append([left, top, width, height])
            scores.append(float(max_scores[idx]))
            class_ids.append(int(max_class_ids[idx]))

    if not boxes:
        return []

    nms_indices = cv2.dnn.NMSBoxes(
        boxes, scores, confidence_thres, iou_thres, eta=0.5, top_k=300
    )

    detections: list[dict] = []
    for idx in nms_indices:
        i = int(np.array(idx).reshape(-1)[0])
        x1, y1, w, h = boxes[i]
        detections.append(
            {
                "bbox": [int(x1), int(y1), int(x1 + w), int(y1 + h)],
                "score": float(scores[i]),
                "label": int(class_ids[i]),
            }
        )
    return detections
