"""PP-OCR DB 检测后处理。"""

from __future__ import annotations

import cv2
import numpy as np
import pyclipper


class DBPostProcess:
    """Differentiable Binarization 后处理（参考 RapidOCR / PaddleOCR）。"""

    def __init__(
        self,
        *,
        thresh: float = 0.3,
        box_thresh: float = 0.5,
        max_candidates: int = 1000,
        unclip_ratio: float = 1.6,
        score_mode: str = "fast",
        use_dilation: bool = True,
    ) -> None:
        self.thresh = thresh
        self.box_thresh = box_thresh
        self.max_candidates = max_candidates
        self.unclip_ratio = unclip_ratio
        self.min_size = 3
        self.score_mode = score_mode
        self.dilation_kernel = np.array([[1, 1], [1, 1]], dtype=np.uint8) if use_dilation else None

    def __call__(
        self,
        pred: np.ndarray,
        ori_shape: tuple[int, int],
    ) -> tuple[np.ndarray, list[float]]:
        src_h, src_w = ori_shape
        prob = pred[:, 0, :, :]
        mask = prob[0] > self.thresh
        if self.dilation_kernel is not None:
            mask = cv2.dilate(mask.astype(np.uint8), self.dilation_kernel) > 0
        boxes, scores = self._boxes_from_bitmap(prob[0], mask, src_w, src_h)
        return self._filter_det_res(boxes, scores, src_h, src_w)

    def _boxes_from_bitmap(
        self,
        prob: np.ndarray,
        bitmap: np.ndarray,
        dest_width: int,
        dest_height: int,
    ) -> tuple[np.ndarray, list[float]]:
        height, width = bitmap.shape
        contours, _ = cv2.findContours(
            (bitmap * 255).astype(np.uint8),
            cv2.RETR_LIST,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        num_contours = min(len(contours), self.max_candidates)
        boxes: list[np.ndarray] = []
        scores: list[float] = []
        for index in range(num_contours):
            contour = contours[index]
            points, short_side = self._get_mini_boxes(contour)
            if short_side < self.min_size:
                continue
            if self.score_mode == "fast":
                score = self._box_score_fast(prob, points.reshape(-1, 2))
            else:
                score = self._box_score_slow(prob, contour)
            if self.box_thresh > score:
                continue
            box = self._unclip(points)
            box, short_side = self._get_mini_boxes(box)
            if short_side < self.min_size + 2:
                continue
            box[:, 0] = np.clip(np.round(box[:, 0] / width * dest_width), 0, dest_width)
            box[:, 1] = np.clip(np.round(box[:, 1] / height * dest_height), 0, dest_height)
            boxes.append(box.astype(np.int32))
            scores.append(float(score))
        if not boxes:
            return np.zeros((0, 4, 2), dtype=np.int32), []
        return np.array(boxes, dtype=np.int32), scores

    def _get_mini_boxes(self, contour: np.ndarray) -> tuple[np.ndarray, float]:
        bounding_box = cv2.minAreaRect(contour)
        points = sorted(list(cv2.boxPoints(bounding_box)), key=lambda item: item[0])
        if points[1][1] > points[0][1]:
            index_1, index_4 = 0, 1
        else:
            index_1, index_4 = 1, 0
        if points[3][1] > points[2][1]:
            index_2, index_3 = 2, 3
        else:
            index_2, index_3 = 3, 2
        box = np.array(
            [points[index_1], points[index_2], points[index_3], points[index_4]],
            dtype=np.float32,
        )
        return box, float(min(bounding_box[1]))

    @staticmethod
    def _box_score_fast(bitmap: np.ndarray, box: np.ndarray) -> float:
        h, w = bitmap.shape[:2]
        points = box.copy()
        xmin = np.clip(np.floor(points[:, 0].min()).astype(np.int32), 0, w - 1)
        xmax = np.clip(np.ceil(points[:, 0].max()).astype(np.int32), 0, w - 1)
        ymin = np.clip(np.floor(points[:, 1].min()).astype(np.int32), 0, h - 1)
        ymax = np.clip(np.ceil(points[:, 1].max()).astype(np.int32), 0, h - 1)
        mask = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
        points[:, 0] -= xmin
        points[:, 1] -= ymin
        cv2.fillPoly(mask, points.reshape(1, -1, 2).astype(np.int32), 1)
        return float(cv2.mean(bitmap[ymin : ymax + 1, xmin : xmax + 1], mask)[0])

    def _box_score_slow(self, bitmap: np.ndarray, contour: np.ndarray) -> float:
        h, w = bitmap.shape[:2]
        contour = contour.reshape(-1, 2).astype(np.float32)
        xmin = np.clip(np.min(contour[:, 0]), 0, w - 1)
        xmax = np.clip(np.max(contour[:, 0]), 0, w - 1)
        ymin = np.clip(np.min(contour[:, 1]), 0, h - 1)
        ymax = np.clip(np.max(contour[:, 1]), 0, h - 1)
        mask = np.zeros((int(ymax - ymin + 1), int(xmax - xmin + 1)), dtype=np.uint8)
        shifted = contour.copy()
        shifted[:, 0] -= xmin
        shifted[:, 1] -= ymin
        cv2.fillPoly(mask, shifted.reshape(1, -1, 2).astype(np.int32), 1)
        return float(cv2.mean(bitmap[int(ymin) : int(ymax) + 1, int(xmin) : int(xmax) + 1], mask)[0])

    def _unclip(self, box: np.ndarray) -> np.ndarray:
        box = box.astype(np.float32)
        area = abs(cv2.contourArea(box))
        length = cv2.arcLength(box, True)
        if length < 1e-6:
            length = 1e-6
        distance = area * self.unclip_ratio / length
        offset = pyclipper.PyclipperOffset()
        offset.AddPath(box, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
        expanded = offset.Execute(distance)
        if not expanded:
            return box.reshape(-1, 1, 2)
        return np.array(expanded[0], dtype=np.float32).reshape(-1, 1, 2)

    def _filter_det_res(
        self,
        dt_boxes: np.ndarray,
        scores: list[float],
        img_height: int,
        img_width: int,
    ) -> tuple[np.ndarray, list[float]]:
        if len(dt_boxes) == 0:
            return dt_boxes, scores
        kept_boxes: list[np.ndarray] = []
        kept_scores: list[float] = []
        for box, score in zip(dt_boxes, scores, strict=True):
            box = self._order_points_clockwise(box)
            box = self._clip_det_res(box, img_height, img_width)
            width = int(np.linalg.norm(box[0] - box[1]))
            height = int(np.linalg.norm(box[0] - box[3]))
            if width <= 3 or height <= 3:
                continue
            kept_boxes.append(box)
            kept_scores.append(score)
        if not kept_boxes:
            return np.zeros((0, 4, 2), dtype=np.int32), []
        return np.array(kept_boxes, dtype=np.int32), kept_scores

    @staticmethod
    def _order_points_clockwise(points: np.ndarray) -> np.ndarray:
        x_sorted = points[np.argsort(points[:, 0]), :]
        left = x_sorted[:2, :]
        right = x_sorted[2:, :]
        left = left[np.argsort(left[:, 1]), :]
        right = right[np.argsort(right[:, 1]), :]
        return np.array([left[0], right[0], right[1], left[1]], dtype=np.float32)

    @staticmethod
    def _clip_det_res(points: np.ndarray, img_height: int, img_width: int) -> np.ndarray:
        clipped = points.copy()
        clipped[:, 0] = np.clip(clipped[:, 0], 0, img_width - 1)
        clipped[:, 1] = np.clip(clipped[:, 1], 0, img_height - 1)
        return clipped
