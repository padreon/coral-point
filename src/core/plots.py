"""Chart generation for coralX — Fase 5 (Lapis 2 & 3 visualisation).

All plot functions save a PNG to output_path and return the path on success,
or None when data is insufficient. matplotlib is imported lazily so the rest
of the app keeps working if it is not installed.

Call export_all_charts(project, output_dir) to generate every applicable chart.
"""
# pylint: disable=import-outside-toplevel,too-many-locals

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.project import Project

# Colour mapping for Gomez & Yap reef health categories (English keys)
_HEALTH_COLORS = {
    "Poor":      "#d62728",
    "Fair":      "#ff7f0e",
    "Good":      "#2ca02c",
    "Excellent": "#1f77b4",
}


def _mpl():
    """Lazy import of matplotlib.pyplot — raises ImportError if not installed."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return plt
    except ImportError as exc:
        raise ImportError(
            "matplotlib is required for chart export. "
            "Install it with: pip install matplotlib>=3.8.0"
        ) from exc


# ---------------------------------------------------------------------------
# Individual plot functions
# ---------------------------------------------------------------------------

def plot_coverage_bar(summary: dict, output_path: str) -> str | None:
    """Horizontal bar chart of benthic coverage % with 95% CI error bars.

    Bars are coloured by benthic group; codes sorted descending by coverage.
    """
    ci_data = summary.get("coverage_ci", {})
    if not ci_data:
        return None

    plt = _mpl()

    codes = sorted(ci_data.keys(), key=lambda c: ci_data[c]["pct"])
    values = [ci_data[c]["pct"] for c in codes]
    xerr_lo = [ci_data[c]["pct"] - ci_data[c]["ci_lower"] for c in codes]
    xerr_hi = [ci_data[c]["ci_upper"] - ci_data[c]["pct"] for c in codes]

    fig, ax = plt.subplots(figsize=(10, max(4, len(codes) * 0.45)))
    y_pos = range(len(codes))
    ax.barh(list(y_pos), values, xerr=[xerr_lo, xerr_hi],
            align="center", color="#4878CF", ecolor="#555555",
            capsize=4, alpha=0.85)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(codes)
    ax.set_xlabel("Coverage (%)")
    ax.set_title("Benthic Coverage (%)", fontweight="bold", pad=12)
    ax.set_xlim(0, min(100, max(values) * 1.25 + 5))
    ax.axvline(0, color="black", linewidth=0.8)

    # Annotate bars
    for i, (v, c) in enumerate(zip(values, codes)):
        ax.text(v + 0.5, i, f"{v:.1f}%", va="center", fontsize=8)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_lifeform_pie(summary: dict, output_path: str) -> str | None:
    """Donut chart of benthic group composition (group_coverage %)."""
    grp_cov = summary.get("group_coverage", {})
    if not grp_cov:
        return None

    plt = _mpl()

    labels = list(grp_cov.keys())
    sizes = [grp_cov[k] for k in labels]

    fig, ax = plt.subplots(figsize=(7, 7))
    wedge_props = {"width": 0.5, "edgecolor": "white", "linewidth": 2}
    wedges, _texts, autotexts = ax.pie(
        sizes,
        labels=None,
        autopct=lambda p: f"{p:.1f}%" if p > 2 else "",
        wedgeprops=wedge_props,
        startangle=90,
    )
    for at in autotexts:
        at.set_fontsize(9)

    ax.legend(wedges, [f"{lbl} ({s:.1f}%)" for lbl, s in zip(labels, sizes)],
              loc="center left", bbox_to_anchor=(1, 0, 0.5, 1), fontsize=9)
    ax.set_title("Life-form Composition", fontweight="bold", pad=16)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_diversity_bar(per_station_rows: list[dict], output_path: str) -> str | None:
    """Grouped bar chart: Shannon H', Simpson 1-D, Hill q1 per station."""
    rows = [r for r in per_station_rows
            if r.get("shannon_H") is not None]
    if not rows:
        return None

    plt = _mpl()
    import numpy as np

    stations = [r["station"] for r in rows]
    shannon = [r.get("shannon_H", 0) for r in rows]
    simpson = [r.get("simpson_1D", 0) for r in rows]
    hill_q1 = [r.get("hill_q1", 0) for r in rows]

    x = np.arange(len(stations))
    width = 0.25

    fig, ax = plt.subplots(figsize=(max(8, len(stations) * 1.2), 6))
    ax.bar(x - width, shannon, width, label="Shannon H'",   color="#4878CF", alpha=0.85)
    ax.bar(x,          simpson, width, label="Simpson 1-D", color="#6ACC65", alpha=0.85)
    ax.bar(x + width,  hill_q1, width, label="Hill q1",     color="#D65F5F", alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(stations, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Index Value")
    ax.set_title("Diversity Indices per Station", fontweight="bold", pad=12)
    ax.legend()
    ax.set_ylim(0)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_mortality_bar(per_station_rows: list[dict], output_path: str) -> str | None:
    """Bar chart of Mortality Index per station.

    Bars turn red when MI > 0.5 (critical threshold). A dashed line marks 0.5.
    """
    rows = [r for r in per_station_rows
            if r.get("mortality_index") is not None]
    if not rows:
        return None

    plt = _mpl()
    import numpy as np

    stations = [r["station"] for r in rows]
    mis = [float(r["mortality_index"]) for r in rows]
    colors = ["#d62728" if m > 0.5 else "#4878CF" for m in mis]

    x = np.arange(len(stations))
    fig, ax = plt.subplots(figsize=(max(7, len(stations) * 1.2), 5))
    bars = ax.bar(x, mis, color=colors, alpha=0.85, edgecolor="white")
    ax.axhline(0.5, color="#555555", linestyle="--", linewidth=1.2,
               label="Critical threshold (0.5)")
    ax.set_xticks(x)
    ax.set_xticklabels(stations, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Mortality Index (MI)")
    ax.set_ylim(0, 1.05)
    ax.set_title("Mortality Index per Station", fontweight="bold", pad=12)
    ax.legend(fontsize=9)

    for rect, mi in zip(bars, mis):
        ax.text(rect.get_x() + rect.get_width() / 2, mi + 0.02,
                f"{mi:.2f}", ha="center", va="bottom", fontsize=8)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_reef_health(per_station_rows: list[dict], output_path: str) -> str | None:
    """Horizontal bar of live coral % per station, coloured by Gomez & Yap category.

    Background zones mark the four classification thresholds (0-25, 25-50, 50-75, 75-100).
    """
    rows = [r for r in per_station_rows
            if r.get("reef_health_category") is not None
            and r.get("group_Hard Coral") is not None]
    if not rows:
        return None

    plt = _mpl()

    stations = [r["station"] for r in rows]
    live_pcts = [float(r.get("group_Hard Coral", 0)) for r in rows]
    categories = [r.get("reef_health_category", "") for r in rows]
    bar_colors = [_HEALTH_COLORS.get(cat, "#aaaaaa") for cat in categories]

    fig, ax = plt.subplots(figsize=(10, max(4, len(stations) * 0.5)))

    # Background zones
    zone_colors = ["#ffd0d0", "#ffe8c0", "#d0f0d0", "#c0dff0"]
    zone_limits = [(0, 25), (25, 50), (50, 75), (75, 100)]
    zone_labels = ["Poor", "Fair", "Good", "Excellent"]
    for (lo, hi), zc, zl in zip(zone_limits, zone_colors, zone_labels):
        ax.axvspan(lo, hi, alpha=0.35, color=zc, label=zl)

    y_pos = range(len(stations))
    ax.barh(list(y_pos), live_pcts, color=bar_colors, alpha=0.9, edgecolor="white")
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(stations, fontsize=9)
    ax.set_xlabel("Live Hard Coral Cover (%)")
    ax.set_xlim(0, 100)
    ax.set_title("Reef Health by Station (Gomez & Yap 1988)", fontweight="bold", pad=12)

    # Annotate bars
    for i, (pct, cat) in enumerate(zip(live_pcts, categories)):
        ax.text(pct + 1, i, f"{pct:.1f}% — {cat}", va="center", fontsize=8)

    ax.legend(loc="lower right", fontsize=8, title="Category")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_ordination(
    pcoa_result: dict,
    sample_names: list[str],
    output_path: str,
) -> str | None:
    """Scatter plot of PCoA axis 1 vs axis 2, labelled by station name."""
    coords = pcoa_result.get("coords")
    if coords is None or coords.shape[0] < 2:
        return None

    plt = _mpl()

    var_exp = pcoa_result.get("variance_explained", [0, 0])
    x = coords[:, 0]
    y = coords[:, 1] if coords.shape[1] > 1 else [0] * len(x)

    fig, ax = plt.subplots(figsize=(8, 7))
    ax.scatter(x, y, s=80, color="#4878CF", alpha=0.85, edgecolors="white", linewidth=0.8)

    for i, name in enumerate(sample_names):
        ax.annotate(name, (x[i], y[i]),
                    textcoords="offset points", xytext=(6, 4), fontsize=8)

    pct1 = f"{var_exp[0]*100:.1f}%" if var_exp else ""
    pct2 = f"{var_exp[1]*100:.1f}%" if len(var_exp) > 1 else ""
    ax.set_xlabel(f"PCoA1 ({pct1})", fontsize=10)
    ax.set_ylabel(f"PCoA2 ({pct2})", fontsize=10)
    ax.axhline(0, color="grey", linewidth=0.5, linestyle="--")
    ax.axvline(0, color="grey", linewidth=0.5, linestyle="--")
    ax.set_title("PCoA Ordination (Bray-Curtis)", fontweight="bold", pad=12)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_dendrogram(
    linkage_result: dict,
    sample_names: list[str],
    output_path: str,
) -> str | None:
    """Hierarchical clustering dendrogram from Bray-Curtis / UPGMA linkage."""
    Z = linkage_result.get("linkage")
    if Z is None or len(sample_names) < 2:
        return None

    plt = _mpl()
    from scipy.cluster.hierarchy import dendrogram

    fig, ax = plt.subplots(figsize=(max(8, len(sample_names) * 1.2), 5))
    dendrogram(Z, labels=sample_names, ax=ax, leaf_rotation=30,
               color_threshold=0.7 * max(Z[:, 2]))
    ax.set_ylabel("Bray-Curtis Dissimilarity")
    method = linkage_result.get("method", "average").upper()
    ax.set_title(f"Hierarchical Clustering ({method})", fontweight="bold", pad=12)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


# ---------------------------------------------------------------------------
# Master export function
# ---------------------------------------------------------------------------

def export_all_charts(project: "Project", output_dir: str) -> list[str]:
    """Generate all applicable charts for project and save to output_dir.

    Returns list of PNG paths that were successfully created.
    Silently skips charts when data is insufficient (returns fewer items).
    Raises ImportError if matplotlib is not installed.
    """
    from src.core.statistics import project_summary, per_station_table
    from src.core.validation import can_run_multivariate

    os.makedirs(output_dir, exist_ok=True)
    paths: list[str] = []

    def _path(name: str) -> str:
        return str(Path(output_dir) / name)

    summary = project_summary(project)
    station_rows = per_station_table(project)

    # 1. Coverage bar
    p = plot_coverage_bar(summary, _path("01_coverage_bar.png"))
    if p:
        paths.append(p)

    # 2. Life-form pie
    p = plot_lifeform_pie(summary, _path("02_lifeform_pie.png"))
    if p:
        paths.append(p)

    # 3. Diversity indices per station
    p = plot_diversity_bar(station_rows, _path("03_diversity_bar.png"))
    if p:
        paths.append(p)

    # 4. Mortality index per station
    p = plot_mortality_bar(station_rows, _path("04_mortality_bar.png"))
    if p:
        paths.append(p)

    # 5. Reef health per station
    p = plot_reef_health(station_rows, _path("05_reef_health.png"))
    if p:
        paths.append(p)

    # 6 & 7: Multivariate charts — only if gate passes
    if can_run_multivariate(project).ok:
        try:
            from src.core.multivariate import (
                composition_matrix, bray_curtis_matrix,
                pcoa, hierarchical_clusters,
            )
            sample_names, _, matrix = composition_matrix(project)
            bc = bray_curtis_matrix(matrix)

            pcoa_result = pcoa(bc)
            p = plot_ordination(pcoa_result, sample_names, _path("06_ordination.png"))
            if p:
                paths.append(p)

            link_result = hierarchical_clusters(bc)
            p = plot_dendrogram(link_result, sample_names, _path("07_dendrogram.png"))
            if p:
                paths.append(p)
        except Exception:
            pass  # multivariate data unavailable — skip silently

    return paths
