"""Dialogs for the four import workflows."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QTextEdit, QRadioButton, QGroupBox, QCheckBox,
)
from PyQt6.QtCore import Qt


class ImportResultDialog(QDialog):
    """Shows a success/error message plus optional warnings after any import."""

    def __init__(self, title: str, message: str, warnings: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)

        icon = "✅" if not warnings or all("not found" not in w for w in warnings) else "⚠️"
        lbl = QLabel(f"{icon}  {message}")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        if warnings:
            layout.addWidget(QLabel("Warnings:"))
            txt = QTextEdit()
            txt.setReadOnly(True)
            txt.setPlainText("\n".join(warnings))
            txt.setMaximumHeight(120)
            layout.addWidget(txt)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btns.accepted.connect(self.accept)
        layout.addWidget(btns)


class CoralCodesMergeDialog(QDialog):
    """
    Shown before importing coral codes — asks whether to merge with
    existing codes or replace them entirely.
    """

    def __init__(self, incoming_count: int, existing_count: int,
                 has_groups: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Coral Codes")
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            f"Found <b>{incoming_count}</b> code(s) in the file.\n"
            f"Project currently has <b>{existing_count}</b> code(s)."
        ))

        merge_box = QGroupBox("Action")
        merge_layout = QVBoxLayout(merge_box)
        self._radio_merge = QRadioButton("Merge — add new codes, keep existing ones")
        self._radio_replace = QRadioButton("Replace — remove all existing codes first")
        self._radio_merge.setChecked(True)
        merge_layout.addWidget(self._radio_merge)
        merge_layout.addWidget(self._radio_replace)
        layout.addWidget(merge_box)

        if has_groups:
            self._chk_groups = QCheckBox("Also import group definitions from file")
            self._chk_groups.setChecked(True)
            layout.addWidget(self._chk_groups)
        else:
            self._chk_groups = None

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    @property
    def merge(self) -> bool:
        return self._radio_merge.isChecked()

    @property
    def import_groups(self) -> bool:
        return bool(self._chk_groups and self._chk_groups.isChecked())


class StationMergeDialog(QDialog):
    """
    Shown before importing station metadata — asks how to handle conflicts
    (existing station with same name).
    """

    def __init__(self, incoming: list[dict], existing_names: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Station Metadata")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)

        overlap = [s["name"] for s in incoming if s["name"] in existing_names]
        new_count = len(incoming) - len(overlap)

        info = f"Found <b>{len(incoming)}</b> station(s) in the file.<br>"
        if new_count:
            info += f"• <b>{new_count}</b> new station(s) will be added.<br>"
        if overlap:
            info += f"• <b>{len(overlap)}</b> existing station(s) match by name."
        lbl = QLabel(info)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        if overlap:
            conflict_box = QGroupBox("For conflicting stations:")
            cb_layout = QVBoxLayout(conflict_box)
            self._radio_update = QRadioButton("Update metadata (depth, GPS, date, notes)")
            self._radio_skip = QRadioButton("Skip — keep existing metadata unchanged")
            self._radio_update.setChecked(True)
            cb_layout.addWidget(self._radio_update)
            cb_layout.addWidget(self._radio_skip)
            layout.addWidget(conflict_box)
        else:
            self._radio_update = None
            self._radio_skip = None

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    @property
    def update_existing(self) -> bool:
        return self._radio_update is None or self._radio_update.isChecked()


class CpceImportDialog(QDialog):
    """
    Shown after a successful CPCe import — asks whether to open as a new
    project or merge stations into the current project.
    """

    def __init__(self, n_stations: int, n_images: int, n_points: int,
                 has_current_project: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import from CPCe Excel")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            f"Successfully read CPCe data:\n"
            f"  • {n_stations} station(s)\n"
            f"  • {n_images} image(s)\n"
            f"  • {n_points} labeled point(s)\n\n"
            "How would you like to import this data?"
        ))

        action_box = QGroupBox("Action")
        ab_layout = QVBoxLayout(action_box)
        self._radio_new = QRadioButton("Open as a new project")
        self._radio_merge = QRadioButton("Merge stations into the current project")
        self._radio_new.setChecked(True)
        if not has_current_project:
            self._radio_merge.setEnabled(False)
        ab_layout.addWidget(self._radio_new)
        ab_layout.addWidget(self._radio_merge)
        layout.addWidget(action_box)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    @property
    def open_as_new(self) -> bool:
        return self._radio_new.isChecked()
