from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import cv2
import numpy as np

from PyQt6.QtCore import QThread, pyqtSignal

if TYPE_CHECKING:
    from src.models.project import ImageAnnotation

try:
    from ultralytics import YOLO as _YOLO  # noqa: F401
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


@dataclass
class LabelResult:
    annotation_path: str
    point_index: int
    predicted_class: str
    mapped_code: str | None
    confidence: float


class AILabeler:
    """Wraps a YOLOv8 classification model for per-point coral code prediction."""

    def __init__(self, model_path: str) -> None:
        from ultralytics import YOLO
        self._model = YOLO(model_path)
        self._class_names: dict[int, str] = self._model.names

    def class_names(self) -> list[str]:
        return list(self._class_names.values())

    def predict_point(
        self,
        image: np.ndarray,
        x: float,
        y: float,
        crop_size: int = 64,
    ) -> tuple[str, float]:
        half = crop_size // 2
        h, w = image.shape[:2]

        x0 = max(0, int(x) - half)
        y0 = max(0, int(y) - half)
        x1 = min(w, int(x) + half)
        y1 = min(h, int(y) + half)

        crop = image[y0:y1, x0:x1]

        pad_top = max(0, half - int(y))
        pad_bottom = max(0, int(y) + half - h)
        pad_left = max(0, half - int(x))
        pad_right = max(0, int(x) + half - w)

        if pad_top or pad_bottom or pad_left or pad_right:
            crop = cv2.copyMakeBorder(
                crop, pad_top, pad_bottom, pad_left, pad_right,
                cv2.BORDER_CONSTANT, value=0,
            )

        results = self._model(crop, verbose=False)
        probs = results[0].probs
        if probs is None:
            raise ValueError(
                "Model does not appear to be a classification model. "
                "Train with `yolo task=classify`."
            )

        class_name = self._class_names[int(probs.top1)]
        confidence = float(probs.top1conf)
        return class_name, confidence

    @staticmethod
    def suggest_mapping(
        class_names: list[str],
        coral_codes: dict[str, str],
    ) -> dict[str, str | None]:
        mapping: dict[str, str | None] = {}
        for cls in class_names:
            matched: str | None = None
            cls_lower = cls.lower().replace("_", " ")
            for code, desc in coral_codes.items():
                if cls_lower == code.lower() or cls_lower in desc.lower():
                    matched = code
                    break
            mapping[cls] = matched
        return mapping


class AILabelWorker(QThread):
    progress = pyqtSignal(int, int, str)
    result_ready = pyqtSignal(list)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self,
        labeler: AILabeler,
        annotations: list[ImageAnnotation],
        class_mapping: dict[str, str | None],
        conf_threshold: float,
        crop_size: int,
        overwrite_labeled: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._labeler = labeler
        self._annotations = annotations
        self._class_mapping = class_mapping
        self._conf_threshold = conf_threshold
        self._crop_size = crop_size
        self._overwrite_labeled = overwrite_labeled
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        results: list[LabelResult] = []
        total = sum(
            len([p for p in a.points if self._overwrite_labeled or p.label is None])
            for a in self._annotations
        )
        done = 0

        try:
            current_path: str | None = None
            current_img: np.ndarray | None = None

            for ann in self._annotations:
                if self._cancelled:
                    break

                img_name = ann.image_path.split("/")[-1].split("\\")[-1]

                if ann.image_path != current_path:
                    current_img = cv2.imread(ann.image_path)
                    current_path = ann.image_path

                if current_img is None:
                    self.progress.emit(
                        done, total,
                        f"WARNING: could not read {img_name} — skipping",
                    )
                    continue

                for p in ann.points:
                    if self._cancelled:
                        break
                    if not self._overwrite_labeled and p.label is not None:
                        continue

                    predicted_class, confidence = self._labeler.predict_point(
                        current_img, p.x, p.y, self._crop_size
                    )

                    mapped_code: str | None = self._class_mapping.get(predicted_class)
                    if confidence < self._conf_threshold:
                        mapped_code = None

                    results.append(LabelResult(
                        annotation_path=ann.image_path,
                        point_index=p.index,
                        predicted_class=predicted_class,
                        mapped_code=mapped_code,
                        confidence=confidence,
                    ))

                    done += 1
                    self.progress.emit(
                        done, total,
                        f"{img_name} — Point #{p.index + 1}: "
                        f"{predicted_class} → {mapped_code or '(skip)'} "
                        f"({confidence:.1%})",
                    )

        except Exception as exc:
            self.error.emit(str(exc))

        self.result_ready.emit(results)
        self.finished.emit()
