"""Statistical comparison utilities for coralX.

Fase 2 — Lapis 2 (bootstrap CI) and Lapis 3 (group tests, temporal/depth analyses).
All functions are pure: no PyQt, no side effects.
"""
# pylint: disable=import-outside-toplevel,broad-exception-caught,too-many-locals

from __future__ import annotations

from typing import Callable

import numpy as np
from scipy import stats

from src.core.validation import validate_metadata_completeness


def bootstrap_ci(
    labels: list[str],
    metric_fn: Callable[[list[str]], float],
    n_boot: int = 1000,
    confidence: float = 0.95,
    seed: int | None = 42,
) -> dict:
    """Bootstrap percentile confidence interval for a label-based metric.

    Resamples labels with replacement n_boot times, computes metric_fn on each
    resample, and returns the percentile-based CI.

    Args:
        labels:    flat list of point labels (one per labeled point).
        metric_fn: function labels -> float (e.g., Shannon H', Simpson 1-D).
        n_boot:    number of bootstrap resamples (default 1000).
        confidence: CI level (default 0.95 = 95% CI).
        seed:      RNG seed for reproducibility.

    Returns:
        {'value': float, 'ci_lower': float, 'ci_upper': float}
    """
    if not labels:
        return {"value": 0.0, "ci_lower": 0.0, "ci_upper": 0.0}

    observed = metric_fn(labels)
    rng = np.random.default_rng(seed)
    arr = np.array(labels)
    boot_vals = np.empty(n_boot)
    for i in range(n_boot):
        sample = list(rng.choice(arr, size=len(arr), replace=True))
        boot_vals[i] = metric_fn(sample)

    alpha = 1 - confidence
    lo = float(np.percentile(boot_vals, alpha / 2 * 100))
    hi = float(np.percentile(boot_vals, (1 - alpha / 2) * 100))
    return {
        "value": round(float(observed), 4),
        "ci_lower": round(lo, 4),
        "ci_upper": round(hi, 4),
    }


def compare_groups(
    values_by_group: dict[str, list[float]],
    method: str = "auto",
) -> dict:
    """Compare a metric across groups using ANOVA or Kruskal-Wallis.

    Args:
        values_by_group: {group_name: [values]}, requires >=2 groups each >=2 values.
        method: 'anova' | 'kruskal' | 'auto'
                'auto' chooses Kruskal-Wallis when any group has n < 10, else ANOVA.

    Returns:
        {'method': str, 'statistic': float, 'p_value': float, 'significant': bool}
        or {'error': str} when data requirements are not met.
    """
    groups = {k: v for k, v in values_by_group.items() if v}
    if len(groups) < 2:
        return {"error": f"Need >=2 groups; got {len(groups)}."}
    for name, vals in groups.items():
        if len(vals) < 2:
            return {"error": f"Group '{name}' has only {len(vals)} value(s); need >=2."}

    chosen = method
    if method == "auto":
        chosen = "kruskal" if any(len(v) < 10 for v in groups.values()) else "anova"

    group_arrays = [np.array(v, dtype=float) for v in groups.values()]
    try:
        if chosen == "anova":
            stat, p = stats.f_oneway(*group_arrays)
        else:
            stat, p = stats.kruskal(*group_arrays)
    except Exception as exc:
        return {"error": str(exc)}

    stat_val = float(stat)  # type: ignore[arg-type]
    p_val = float(p)  # type: ignore[arg-type]
    return {
        "method": chosen,
        "statistic": round(stat_val, 6),
        "p_value": round(p_val, 6),
        "significant": bool(p_val < 0.05),
    }


def temporal_trend(project: object, metric: str = "live_coral_pct") -> dict:
    """Linear temporal trend for a metric across survey dates.

    Requires validate_metadata_completeness(project)['temporal'].ok == True.
    Returns per-station results with slope, p_value, and trend direction.

    Args:
        project: Project instance.
        metric:  one of 'live_coral_pct', 'mortality_index', 'shannon'.

    Returns:
        {
          'ok': bool,
          'reason': str | None,
          'stations': {
            station_name: {
              'dates': [str, ...],
              'values': [float, ...],
              'slope': float,
              'p_value': float,
              'trend': 'naik' | 'turun' | 'stabil'
            }
          }
        }
    """
    meta = validate_metadata_completeness(project)
    if not meta["temporal"].ok:
        return {"ok": False, "reason": "; ".join(meta["temporal"].reasons), "stations": {}}

    from src.core.statistics import station_summary

    coral_groups = getattr(project, "coral_groups", [])
    results: dict = {}
    for st in getattr(project, "stations", []):
        d = getattr(st, "date", None)
        if not d:
            continue
        summary = station_summary(st, coral_groups)
        value = _extract_metric(summary, metric)
        if value is None:
            continue
        sname = st.name
        if sname not in results:
            results[sname] = {"dates": [], "values": []}
        results[sname]["dates"].append(str(d))
        results[sname]["values"].append(value)

    station_trends: dict = {}
    for sname, data in results.items():
        dates = data["dates"]
        values = data["values"]
        if len(dates) < 2:
            continue
        # Convert ISO dates to ordinal numbers for regression
        from datetime import date as _date
        x = np.array([_date.fromisoformat(d).toordinal() for d in dates], dtype=float)
        y = np.array(values, dtype=float)
        result = stats.linregress(x, y)
        slope = float(result.slope)
        p = float(result.pvalue)
        if p >= 0.05:
            trend = "stabil"
        elif slope > 0:
            trend = "naik"
        else:
            trend = "turun"
        station_trends[sname] = {
            "dates": dates,
            "values": values,
            "slope": round(slope, 6),
            "p_value": round(p, 6),
            "trend": trend,
        }

    return {"ok": True, "reason": None, "stations": station_trends}


def depth_gradient(project: object, metric: str = "live_coral_pct") -> dict:
    """Linear regression of a metric against depth across stations.

    Requires validate_metadata_completeness(project)['depth'].ok == True.

    Returns:
        {
          'ok': bool,
          'reason': str | None,
          'slope': float,
          'r_squared': float,
          'p_value': float,
          'points': [(depth, value), ...]
        }
    """
    meta = validate_metadata_completeness(project)
    if not meta["depth"].ok:
        return {"ok": False, "reason": "; ".join(meta["depth"].reasons), "slope": None,
                "r_squared": None, "p_value": None, "points": []}

    from src.core.statistics import station_summary

    coral_groups = getattr(project, "coral_groups", [])
    points: list[tuple[float, float]] = []
    for st in getattr(project, "stations", []):
        dm = getattr(st, "depth_m", None)
        if dm is None or float(dm) <= 0:
            continue
        summary = station_summary(st, coral_groups)
        value = _extract_metric(summary, metric)
        if value is None:
            continue
        points.append((float(dm), value))

    if len(points) < 3:
        return {
            "ok": False,
            "reason": f"Need >=3 stations with both depth and metric; found {len(points)}.",
            "slope": None, "r_squared": None, "p_value": None, "points": points,
        }

    x = np.array([p[0] for p in points], dtype=float)
    y = np.array([p[1] for p in points], dtype=float)
    result = stats.linregress(x, y)
    return {
        "ok": True,
        "reason": None,
        "slope": round(float(result.slope), 6),
        "r_squared": round(float(result.rvalue ** 2), 4),
        "p_value": round(float(result.pvalue), 6),
        "points": points,
    }


def _extract_metric(summary: dict, metric: str) -> float | None:
    """Extract a named metric from a station_summary dict."""
    if metric == "live_coral_pct":
        return summary.get("group_coverage", {}).get("Hard Coral")
    if metric == "mortality_index":
        return summary.get("mortality_index")
    if metric == "shannon":
        return summary.get("shannon_diversity")
    return None
