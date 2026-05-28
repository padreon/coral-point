"""Dialog for calibrating image scale: user clicks two points and enters real-world distance."""

import math
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox,
    QComboBox, QCheckBox, QPushButton, QWidget,
    QDialogButtonBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QPixmap, QBrush, QFont

from src.models.project import ImageAnnotation


POINT_RADIUS = 6
PREVIEW_MAX_SIZE = 600


class _CalibCanvas(QWidget):
    """Minimal canvas that lets the user click exactly two calibration points."""

    points_changed = pyqtSignal(list)   # emits list of (x, y) in image coords

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._orig = pixmap
        self._clicks: list[tuple[int, int]] = []

        # Scale pixmap to fit PREVIEW_MAX_SIZE
        self._pixmap = pixmap.scaled(
            PREVIEW_MAX_SIZE, PREVIEW_MAX_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._scale = self._pixmap.width() / pixmap.width()

        self.setFixedSize(self._pixmap.size())
        self.setCursor(Qt.CursorShape.CrossCursor)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if len(self._clicks) >= 2:
            self._clicks.clear()
        px = event.position().x()
        py = event.position().y()
        # convert screen → image coords
        ix = int(px / self._scale)
        iy = int(py / self._scale)
        self._clicks.append((ix, iy))
        self.points_changed.emit(list(self._clicks))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._pixmap)

        if len(self._clicks) == 2:
            # draw line between points
            ax = int(self._clicks[0][0] * self._scale)
            ay = int(self._clicks[0][1] * self._scale)
            bx = int(self._clicks[1][0] * self._scale)
            by = int(self._clicks[1][1] * self._scale)
            pen = QPen(QColor(255, 220, 0), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(ax, ay, bx, by)

        pen = QPen(QColor(255, 80, 80), 2)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor(255, 80, 80, 180)))
        font = QFont()
        font.setBold(True)
        painter.setFont(font)

        for i, (ix, iy) in enumerate(self._clicks):
            sx = int(ix * self._scale)
            sy = int(iy * self._scale)
            painter.drawEllipse(
                sx - POINT_RADIUS, sy - POINT_RADIUS,
                POINT_RADIUS * 2, POINT_RADIUS * 2,
            )
            painter.setPen(QPen(Qt.GlobalColor.white))
            painter.drawText(sx - 4, sy + 5, str(i + 1))
            painter.setPen(pen)

    def reset(self):
        self._clicks.clear()
        self.points_changed.emit([])
        self.update()

    def pixel_distance(self) -> float | None:
        if len(self._clicks) < 2:
            return None
        dx = self._clicks[1][0] - self._clicks[0][0]
        dy = self._clicks[1][1] - self._clicks[0][1]
        return math.sqrt(dx * dx + dy * dy)


class CalibrationDialog(QDialog):
    """
    Modal dialog for setting the pixel-per-unit scale of an image.

    Emits calibration_applied(scale_factor, scale_unit, apply_to_all)
    where scale_factor = pixels per unit.
    """

    calibration_applied = pyqtSignal(float, str, bool)  # scale_factor, unit, apply_all

    def __init__(self, annotation: ImageAnnotation, parent=None):
        super().__init__(parent)
        self._ann = annotation
        self.setWindowTitle("Calibrate Image Scale")
        self.setModal(True)

        pixmap = QPixmap(annotation.image_path)
        if pixmap.isNull():
            pixmap = QPixmap(PREVIEW_MAX_SIZE, PREVIEW_MAX_SIZE)
            pixmap.fill(QColor(40, 40, 40))

        self._canvas = _CalibCanvas(pixmap, self)
        self._canvas.points_changed.connect(self._on_points_changed)

        # Controls
        self._lbl_instruction = QLabel(
            "Step 1: Click two points on a known feature (e.g. scale bar or ruler).\n"
            "Step 2: Enter the real-world distance between those points."
        )
        self._lbl_instruction.setWordWrap(True)

        self._lbl_px_dist = QLabel("Pixel distance: —")

        dist_layout = QHBoxLayout()
        self._spin_dist = QDoubleSpinBox()
        self._spin_dist.setRange(0.01, 100000)
        self._spin_dist.setDecimals(2)
        self._spin_dist.setValue(50.0)
        self._spin_dist.setSuffix("")
        self._spin_dist.valueChanged.connect(self._update_preview)

        self._combo_unit = QComboBox()
        self._combo_unit.addItems(["cm", "m"])
        idx = 0 if annotation.scale_unit == "cm" else 1
        self._combo_unit.setCurrentIndex(idx)
        self._combo_unit.currentTextChanged.connect(self._update_preview)

        dist_layout.addWidget(QLabel("Real-world distance:"))
        dist_layout.addWidget(self._spin_dist)
        dist_layout.addWidget(self._combo_unit)
        dist_layout.addStretch()

        self._lbl_scale_preview = QLabel("Scale factor: —")
        self._lbl_area_preview = QLabel("Photo area: —")

        self._chk_apply_all = QCheckBox("Apply this scale to all images in this station")
        self._chk_apply_all.setChecked(False)

        btn_reset = QPushButton("Reset points")
        btn_reset.clicked.connect(self._canvas.reset)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        _ok_btn = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        if _ok_btn is not None:
            _ok_btn.setText("Apply Calibration")
            _ok_btn.setEnabled(False)
        self._buttons.accepted.connect(self._apply)
        self._buttons.rejected.connect(self.reject)

        # Pre-fill existing calibration
        if annotation.scale_factor > 1.0:
            self._lbl_scale_preview.setText(
                f"Current: {annotation.scale_factor:.2f} px/{annotation.scale_unit}"
            )

        layout = QVBoxLayout(self)
        layout.addWidget(self._lbl_instruction)
        layout.addWidget(self._canvas)
        layout.addWidget(self._lbl_px_dist)
        layout.addLayout(dist_layout)
        layout.addWidget(self._lbl_scale_preview)
        layout.addWidget(self._lbl_area_preview)
        layout.addWidget(btn_reset)
        layout.addWidget(self._chk_apply_all)
        layout.addWidget(self._buttons)
        self.setLayout(layout)

    def _on_points_changed(self, pts: list):
        px_dist = self._canvas.pixel_distance()
        _ok_btn = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        if px_dist is not None:
            self._lbl_px_dist.setText(f"Pixel distance: {px_dist:.1f} px")
            if _ok_btn is not None:
                _ok_btn.setEnabled(True)
        else:
            self._lbl_px_dist.setText("Pixel distance: —")
            if _ok_btn is not None:
                _ok_btn.setEnabled(False)
        self._update_preview()

    def _update_preview(self):
        px_dist = self._canvas.pixel_distance()
        if px_dist is None or px_dist == 0:
            self._lbl_scale_preview.setText("Scale factor: —")
            self._lbl_area_preview.setText("Photo area: —")
            return

        real_dist = self._spin_dist.value()
        unit = self._combo_unit.currentText()
        sf = px_dist / real_dist
        self._lbl_scale_preview.setText(f"Scale factor: {sf:.3f} px/{unit}")

        w = self._ann.image_width
        h = self._ann.image_height
        if w and h and sf > 0:
            area = (w / sf) * (h / sf)
            self._lbl_area_preview.setText(
                f"Photo area: {area:.2f} {unit}² "
                f"({w/sf:.1f} × {h/sf:.1f} {unit})"
            )
        else:
            self._lbl_area_preview.setText("Photo area: —")

    def _apply(self):
        px_dist = self._canvas.pixel_distance()
        if not px_dist or px_dist == 0:
            return
        real_dist = self._spin_dist.value()
        unit = self._combo_unit.currentText()
        sf = px_dist / real_dist
        apply_all = self._chk_apply_all.isChecked()
        self.calibration_applied.emit(sf, unit, apply_all)
        self.accept()
