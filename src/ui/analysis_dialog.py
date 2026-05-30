"""Advanced analysis dialog (Lapis 3) for coralX.

Opens from menu Analisa → Analisa Lanjutan…
Checkboxes for each advanced analysis are automatically disabled when
their prerequisites are not met, with tooltips explaining why.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QCheckBox, QComboBox, QLabel, QDialogButtonBox, QFileDialog, QMessageBox,
)

from src.core.validation import (
    can_run_multivariate,
    validate_metadata_completeness,
    validate_sampling_consistency,
)


class AnalysisDialog(QDialog):
    """Dialog for configuring and running advanced (Lapis 3) analyses."""

    def __init__(self, project: object, parent=None) -> None:
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("Analisa Lanjutan")
        self.setMinimumWidth(480)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Run validation once
        meta = validate_metadata_completeness(self.project)
        mv_gate = can_run_multivariate(self.project)
        sampling = validate_sampling_consistency(self.project)

        # ---------- Multivariat group ----------
        mv_box = QGroupBox("Multivariat (Bray-Curtis / PCoA / PERMANOVA / SIMPER)")
        mv_layout = QVBoxLayout(mv_box)

        self.cb_bray = QCheckBox("Matriks Bray-Curtis")
        self.cb_pcoa = QCheckBox("Ordinasi PCoA")
        self.cb_permanova = QCheckBox("PERMANOVA")
        self.cb_simper = QCheckBox("SIMPER")

        mv_reason = " | ".join(mv_gate.reasons) if not mv_gate.ok else ""
        for cb in (self.cb_bray, self.cb_pcoa, self.cb_permanova, self.cb_simper):
            cb.setEnabled(mv_gate.ok)
            if not mv_gate.ok:
                cb.setToolTip(mv_reason)
            mv_layout.addWidget(cb)

        # Bray-Curtis options
        opt_layout = QHBoxLayout()
        opt_layout.addWidget(QLabel("Biotic only:"))
        self.combo_biotic = QComboBox()
        self.combo_biotic.addItems(["Ya (default)", "Tidak"])
        self.combo_biotic.setEnabled(mv_gate.ok)
        opt_layout.addWidget(self.combo_biotic)
        opt_layout.addWidget(QLabel("Transform:"))
        self.combo_transform = QComboBox()
        self.combo_transform.addItems(["none", "sqrt", "fourth_root"])
        self.combo_transform.setEnabled(mv_gate.ok)
        opt_layout.addWidget(self.combo_transform)
        opt_layout.addStretch()
        mv_layout.addLayout(opt_layout)

        layout.addWidget(mv_box)

        # ---------- Temporal group ----------
        tmp_box = QGroupBox("Analisa Temporal (tren waktu)")
        tmp_layout = QVBoxLayout(tmp_box)
        self.cb_temporal = QCheckBox("Hitung tren temporal per stasiun")
        tmp_ok = meta["temporal"].ok
        self.cb_temporal.setEnabled(tmp_ok)
        if not tmp_ok:
            self.cb_temporal.setToolTip(" | ".join(meta["temporal"].reasons))
        tmp_layout.addWidget(self.cb_temporal)
        layout.addWidget(tmp_box)

        # ---------- Depth gradient group ----------
        dep_box = QGroupBox("Gradien Kedalaman")
        dep_layout = QVBoxLayout(dep_box)
        self.cb_depth = QCheckBox("Regresi metrik vs kedalaman (depth_m)")
        dep_ok = meta["depth"].ok
        self.cb_depth.setEnabled(dep_ok)
        if not dep_ok:
            self.cb_depth.setToolTip(" | ".join(meta["depth"].reasons))
        dep_layout.addWidget(self.cb_depth)
        layout.addWidget(dep_box)

        # ---------- Spatial / Map Data group ----------
        spa_box = QGroupBox("Data Peta (GPS + metrik)")
        spa_layout = QVBoxLayout(spa_box)
        self.cb_spatial = QCheckBox("Export sheet Map Data (GIS-ready)")
        spa_ok = meta["spatial"].ok
        self.cb_spatial.setEnabled(spa_ok)
        if not spa_ok:
            self.cb_spatial.setToolTip(" | ".join(meta["spatial"].reasons))
        spa_layout.addWidget(self.cb_spatial)
        layout.addWidget(spa_box)

        # ---------- Warnings banner ----------
        warnings = sampling.warnings
        if warnings:
            warn_label = QLabel("⚠ " + "\n⚠ ".join(warnings))
            warn_label.setWordWrap(True)
            warn_label.setStyleSheet("color: #b8860b; font-size: 10px;")
            layout.addWidget(warn_label)

        # ---------- Buttons ----------
        btn_box = QDialogButtonBox()
        self.run_btn = btn_box.addButton("Jalankan & Export…", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self._run_export)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _run_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Simpan Hasil Analisa Lanjutan", "", "Excel (*.xlsx)"
        )
        if not path:
            return

        opts = {
            "bray_curtis": self.cb_bray.isChecked(),
            "pcoa": self.cb_pcoa.isChecked(),
            "permanova": self.cb_permanova.isChecked(),
            "simper": self.cb_simper.isChecked(),
            "temporal": self.cb_temporal.isChecked(),
            "depth": self.cb_depth.isChecked(),
            "spatial": self.cb_spatial.isChecked(),
            "biotic_only": self.combo_biotic.currentIndex() == 0,
            "transform": self.combo_transform.currentText(),
        }

        try:
            _run_advanced_export(self.project, path, opts)
            QMessageBox.information(self, "Selesai", f"Hasil disimpan ke:\n{path}")
            self.accept()
        except Exception as exc:
            QMessageBox.warning(self, "Gagal", str(exc))


def _run_advanced_export(project: object, output_path: str, opts: dict) -> None:
    """Write an Excel file with only the selected advanced analyses."""
    import pandas as pd

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        any_sheet = False

        # --- Multivariat ---
        if any(opts.get(k) for k in ("bray_curtis", "pcoa", "permanova", "simper")):
            from src.core.multivariate import (
                composition_matrix, bray_curtis_matrix, pcoa,
                permanova, simper,
            )
            sample_names, code_names, matrix = composition_matrix(
                project,
                biotic_only=opts.get("biotic_only", True),
                transform=opts.get("transform", "none"),
            )
            bc = bray_curtis_matrix(matrix)

            if opts.get("bray_curtis"):
                bc_df = pd.DataFrame(bc, index=sample_names, columns=sample_names).round(4)
                bc_df.to_excel(writer, sheet_name="Bray-Curtis")
                any_sheet = True

            if opts.get("pcoa"):
                pcoa_result = pcoa(bc)
                coords = pcoa_result["coords"]
                n_axes = coords.shape[1] if coords.ndim == 2 else 0
                ord_rows = []
                for i, name in enumerate(sample_names):
                    row: dict = {"station": name}
                    for ax in range(n_axes):
                        row[f"PCoA{ax+1}"] = round(float(coords[i, ax]), 6)
                    ord_rows.append(row)
                var_exp = pcoa_result["variance_explained"]
                var_row: dict = {"station": "Variance explained"}
                for ax in range(n_axes):
                    var_row[f"PCoA{ax+1}"] = var_exp[ax] if ax < len(var_exp) else ""
                ord_rows.append(var_row)
                pd.DataFrame(ord_rows).to_excel(writer, sheet_name="Ordination", index=False)
                any_sheet = True

            if opts.get("permanova"):
                perm_result = permanova(bc, sample_names)
                if "error" in perm_result:
                    pd.DataFrame([{"Note": perm_result["error"]}]).to_excel(
                        writer, sheet_name="PERMANOVA", index=False)
                else:
                    perm_rows = [
                        {"Metric": "pseudo-F", "Value": perm_result.get("pseudo_F")},
                        {"Metric": "p-value", "Value": perm_result.get("p_value")},
                        {"Metric": "permutations", "Value": perm_result.get("permutations")},
                        {"Metric": "significant (p<0.05)",
                         "Value": str(perm_result.get("significant"))},
                    ]
                    pd.DataFrame(perm_rows).to_excel(writer, sheet_name="PERMANOVA", index=False)
                any_sheet = True

            if opts.get("simper") and len(sample_names) >= 2:
                simper_result = simper(
                    matrix, code_names, sample_names,
                    sample_names[0], sample_names[1],
                )
                if simper_result:
                    pd.DataFrame(simper_result).to_excel(writer, sheet_name="SIMPER", index=False)
                    any_sheet = True

        # --- Temporal ---
        if opts.get("temporal"):
            from src.core.comparison import temporal_trend
            trend = temporal_trend(project)
            if trend.get("ok"):
                rows = []
                for sname, data in trend["stations"].items():
                    for d, v in zip(data["dates"], data["values"]):
                        rows.append({"station": sname, "date": d, "value": v})
                if rows:
                    pd.DataFrame(rows).to_excel(writer, sheet_name="Temporal", index=False)
                    any_sheet = True
            else:
                pd.DataFrame([{"Reason": trend.get("reason")}]).to_excel(
                    writer, sheet_name="Temporal", index=False)
                any_sheet = True

        # --- Depth gradient ---
        if opts.get("depth"):
            from src.core.comparison import depth_gradient
            dg = depth_gradient(project)
            if dg.get("ok"):
                dg_rows = [
                    {"Metric": "slope", "Value": dg.get("slope")},
                    {"Metric": "r_squared", "Value": dg.get("r_squared")},
                    {"Metric": "p_value", "Value": dg.get("p_value")},
                ]
                pd.DataFrame(dg_rows).to_excel(writer, sheet_name="Depth Gradient", index=False)
                any_sheet = True

        # --- Map Data ---
        if opts.get("spatial"):
            from src.core.statistics import station_summary
            coral_groups = getattr(project, "coral_groups", [])
            map_rows = []
            for st in getattr(project, "stations", []):
                lat = getattr(st, "gps_lat", None)
                lon = getattr(st, "gps_lon", None)
                if not lat or not lon:
                    continue
                summ = station_summary(st, coral_groups)
                reef = summ.get("reef_health") or {}
                map_rows.append({
                    "station": st.name,
                    "lat": lat,
                    "lon": lon,
                    "live_coral_pct": summ.get("group_coverage", {}).get("Hard Coral", ""),
                    "mortality_index": summ.get("mortality_index", ""),
                    "reef_health": reef.get("category", ""),
                })
            if map_rows:
                pd.DataFrame(map_rows).to_excel(writer, sheet_name="Map Data", index=False)
                any_sheet = True

        if not any_sheet:
            pd.DataFrame([{"Note": "Tidak ada analisa yang dipilih."}]).to_excel(
                writer, sheet_name="Info", index=False)
