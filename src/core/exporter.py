import json
import numpy as np
import pandas as pd
from pathlib import Path
from src.models.project import Project
from src.core.statistics import project_summary, per_image_table, per_station_table
from src.core.analysis import photo_area, cover_area_per_code


def export_csv(project: Project, output_path: str) -> str:
    """Export per-image coverage table to CSV (includes station column)."""
    rows = per_image_table(project)
    df = pd.DataFrame(rows).fillna(0)
    df.to_csv(output_path, index=False)
    return output_path


def export_excel(project: Project, output_path: str) -> str:
    """
    Export to Excel with sheets:
    - Summary: overall project statistics including extended diversity indices
    - Group Coverage: aggregated per benthic group (Hard Coral / Soft Algae / Substrate)
    - Per Station: coverage + diversity per station
    - Per Image: coverage per image with 95% CI columns
    - Cover Area: photo area and per-code area (only when calibrated)
    - Raw Points: every labeled point
    """
    summary = project_summary(project)
    per_station = per_station_table(project)
    per_image = per_image_table(project)

    # Raw points (with station column)
    raw_rows = []
    for station in project.stations:
        for ann in station.annotations:
            for p in ann.points:
                raw_rows.append({
                    "station": station.name,
                    "image": ann.image_path,
                    "point_index": p.index,
                    "x": round(p.x, 2),
                    "y": round(p.y, 2),
                    "label": p.label or "",
                    "category": p.category or "",
                })

    # Summary sheet — 4 columns: Metric / Value / CI Lower / CI Upper
    # Coverage rows use the CI columns; other rows leave them blank.
    _col = {"Metric": "", "Value": "", "95% CI Lower (%)": "", "95% CI Upper (%)": ""}

    def _row(metric: str, value: object, ci_lower: object = "", ci_upper: object = "") -> dict:
        return {"Metric": metric, "Value": value,
                "95% CI Lower (%)": ci_lower, "95% CI Upper (%)": ci_upper}

    summary_rows: list[dict] = []
    if summary:
        summary_rows += [
            _row("Total points",            summary["total_points"]),
            _row("Labeled points",          summary["labeled_points"]),
            _row(""),
            _row("Species richness (S)",    summary.get("species_richness", "")),
            _row("Shannon diversity (H')",  summary.get("shannon_diversity", "")),
            _row("Simpson diversity (1-D)", summary.get("simpson_diversity", "")),
            _row("Pielou evenness (J')",    summary.get("pielou_evenness", "")),
            _row("Margalef richness (d)",   summary.get("margalef_richness", "")),
            _row("Fisher alpha (α)",        summary.get("fisher_alpha", "")),
            _row(""),
        ]
        for label, info in summary.get("coverage_ci", {}).items():
            summary_rows.append(_row(
                f"Coverage — {label}",
                info["pct"],
                info["ci_lower"],
                info["ci_upper"],
            ))
        if summary.get("group_coverage"):
            summary_rows.append(_row(""))
            for grp, pct in summary["group_coverage"].items():
                summary_rows.append(_row(f"Group — {grp}", pct))

    # Group coverage sheet: one row per station + project total
    grp_rows: list[dict] = []
    all_grp_names: set[str] = set()
    for station in project.stations:
        from src.core.statistics import station_summary
        st_sum = station_summary(station, project.coral_groups)
        grp_cov = st_sum.get("group_coverage", {})
        all_grp_names.update(grp_cov.keys())
        row: dict = {"station": station.name}
        row.update(grp_cov)
        grp_rows.append(row)
    # Project total row
    if summary.get("group_coverage"):
        total_row: dict = {"station": "PROJECT TOTAL"}
        total_row.update(summary["group_coverage"])
        grp_rows.append(total_row)

    # Cover area sheet (only for calibrated annotations)
    cover_rows: list[dict] = []
    for station in project.stations:
        for ann in station.annotations:
            p_area = photo_area(ann)
            if p_area is None:
                continue
            c_area = cover_area_per_code(ann) or {}
            row = {
                "station": station.name,
                "image": ann.image_path,
                f"photo_area_{ann.scale_unit}2": p_area,
                "scale_factor_px_per_unit": ann.scale_factor,
                "scale_unit": ann.scale_unit,
            }
            for code, area in c_area.items():
                row[f"{code}_{ann.scale_unit}2"] = area
            cover_rows.append(row)

    # Statistics sheet: mean, std dev, std error per code across all images
    stats_rows = _coverage_statistics(project)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame(grp_rows).fillna(0).to_excel(writer, sheet_name="Group Coverage", index=False)
        pd.DataFrame(per_station).fillna(0).to_excel(writer, sheet_name="Per Station", index=False)
        pd.DataFrame(per_image).fillna(0).to_excel(writer, sheet_name="Per Image", index=False)
        pd.DataFrame(stats_rows).to_excel(writer, sheet_name="Statistics", index=False)
        if cover_rows:
            pd.DataFrame(cover_rows).fillna(0).to_excel(writer, sheet_name="Cover Area", index=False)
        pd.DataFrame(raw_rows).to_excel(writer, sheet_name="Raw Points", index=False)

    return output_path


def _coverage_statistics(project: Project) -> list[dict]:
    """Per-code mean, std dev, and std error across all images in the project."""
    all_annotations = project.annotations
    if not all_annotations:
        return []

    per_image = [ann.coverage_stats() for ann in all_annotations]
    all_codes = sorted({code for row in per_image for code in row})
    n = len(per_image)

    matrix = np.array(
        [[row.get(code, 0.0) for code in all_codes] for row in per_image],
        dtype=float,
    )

    means  = matrix.mean(axis=0)
    stds   = matrix.std(axis=0, ddof=1) if n > 1 else np.zeros(len(all_codes))
    errors = stds / np.sqrt(n) if n > 0 else np.zeros(len(all_codes))

    return [
        {
            "Code":          code,
            "Mean (%)":      round(float(means[i]),  4),
            "Std Dev (%)":   round(float(stds[i]),   4),
            "Std Error (%)": round(float(errors[i]), 4),
        }
        for i, code in enumerate(all_codes)
    ]


def export_coral_codes(project: Project, output_path: str) -> str:
    """
    Export project coral codes to JSON or CSV.

    JSON (.json) — full round-trip format:
      {
        "codes":  {"HC": "Hard Coral", ...},
        "groups": [{"name": "Coral", "codes": ["HC", ...], "color": "FF8000"}, ...]
      }
      Re-importable via File → Import → Coral Codes.

    CSV (.csv / .tsv) — flat table with columns: code, description, group, color.
      One row per code; group and color come from coral_groups (empty if ungrouped).
    """
    ext = Path(output_path).suffix.lower()

    # Build code → group name and color lookup
    code_to_group: dict[str, str] = {}
    code_to_color: dict[str, str] = {}
    for g in project.coral_groups:
        grp_name = g.get("name", "")
        grp_color = g.get("color", "")
        for c in g.get("codes", []):
            code_to_group[c] = grp_name
            code_to_color[c] = grp_color

    if ext == ".json":
        data = {
            "codes": project.coral_codes,
            "groups": project.coral_groups,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    elif ext in (".csv", ".tsv"):
        sep = "\t" if ext == ".tsv" else ","
        rows = [
            {
                "code": code,
                "description": desc,
                "group": code_to_group.get(code, ""),
                "color": code_to_color.get(code, ""),
            }
            for code, desc in project.coral_codes.items()
        ]
        pd.DataFrame(rows).to_csv(output_path, index=False, sep=sep)

    else:
        raise ValueError(f"Unsupported format: {ext}. Use .json, .csv, or .tsv")

    return output_path
