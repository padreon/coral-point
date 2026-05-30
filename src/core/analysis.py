"""Extended analysis functions for coral reef point count data."""

import math
from typing import Optional

from scipy.optimize import brentq

from src.models.project import ImageAnnotation


def species_richness(labels: list[str]) -> int:
    """Number of unique codes present (S)."""
    return len(set(labels))


def pielou_evenness(H_prime: float, S: int) -> float:
    """Pielou's J' = H' / ln(S). Range 0–1; 1 = perfectly even distribution."""
    if S <= 1 or H_prime <= 0:
        return 0.0
    return H_prime / math.log(S)


def margalef_richness(S: int, N: int) -> float:
    """Margalef's d = (S - 1) / ln(N). Species richness relative to sample size."""
    if N <= 1 or S <= 0:
        return 0.0
    return (S - 1) / math.log(N)


def fisher_alpha(S: int, N: int) -> float:
    """Fisher's alpha diversity index via iterative solver.

    Solves: S = alpha * ln(1 + N/alpha)
    Uses brentq root-finding on the interval [1e-6, N].
    """
    if S <= 0 or N <= 0 or S >= N:
        return 0.0
    try:
        def equation(alpha: float) -> float:
            return alpha * math.log(1 + N / alpha) - S
        return float(brentq(equation, 1e-6, N * 10))
    except Exception:
        return 0.0


def wilson_confidence_interval(
    n_hits: int,
    n_total: int,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """95% CI for a proportion using the Wilson score interval.

    More accurate than normal approximation for small n or extreme proportions.
    Returns (lower%, upper%) as percentages (0–100).
    """
    if n_total == 0:
        return (0.0, 0.0)
    from scipy.stats import norm
    z = float(norm.ppf(1 - (1 - confidence) / 2))
    p = n_hits / n_total
    centre = (p + z**2 / (2 * n_total)) / (1 + z**2 / n_total)
    margin = (z / (1 + z**2 / n_total)) * math.sqrt(
        p * (1 - p) / n_total + z**2 / (4 * n_total**2)
    )
    lower = max(0.0, (centre - margin) * 100)
    upper = min(100.0, (centre + margin) * 100)
    return (round(lower, 2), round(upper, 2))


def group_coverage(labels: list[str], coral_groups: list[dict]) -> dict[str, float]:
    """% cover aggregated per group using project.coral_groups mapping.

    coral_groups format: [{"name": "Hard Coral", "codes": ["HC", "CCA", "ZO"]}, ...]
    Returns {"Hard Coral": 42.3, "Soft / Algae": 18.1, "Substrate": 25.0, "Uncategorized": 14.6}
    """
    if not labels:
        return {}

    total = len(labels)
    counts: dict[str, int] = {}
    for lbl in labels:
        counts[lbl] = counts.get(lbl, 0) + 1

    # Build code → group map
    code_to_group: dict[str, str] = {}
    for group in coral_groups:
        for code in group.get("codes", []):
            code_to_group[code] = group["name"]

    group_counts: dict[str, int] = {}
    uncategorized = 0
    for code, cnt in counts.items():
        grp = code_to_group.get(code)
        if grp:
            group_counts[grp] = group_counts.get(grp, 0) + cnt
        else:
            uncategorized += cnt

    result = {k: round(v / total * 100, 2) for k, v in group_counts.items()}
    if uncategorized:
        result["Uncategorized"] = round(uncategorized / total * 100, 2)
    return result


def photo_area(annotation: ImageAnnotation) -> Optional[float]:
    """Effective photo area in scale_unit² (cm² or m²).

    Returns None if scale_factor is not calibrated (== 1.0 or == 0).
    Accounts for border_exclusion (pixel border) or border_rect if set.
    """
    sf = annotation.scale_factor
    if sf <= 1.0:
        return None

    w = annotation.image_width
    h = annotation.image_height

    # Determine effective region
    if hasattr(annotation, "border_rect") and annotation.border_rect:
        x_min, y_min, x_max, y_max = annotation.border_rect
        eff_w = x_max - x_min
        eff_h = y_max - y_min
    else:
        b = getattr(annotation, "border_exclusion", 0) or 0
        eff_w = max(0, w - 2 * b)
        eff_h = max(0, h - 2 * b)

    area = (eff_w / sf) * (eff_h / sf)
    return round(area, 4)


def cover_area_per_code(annotation: ImageAnnotation) -> Optional[dict[str, float]]:
    """Actual area (unit²) per code = photo_area × (count_code / total_labeled).

    Returns None if not calibrated.
    """
    p_area = photo_area(annotation)
    if p_area is None:
        return None

    labeled = [pt for pt in annotation.points if pt.label]
    if not labeled:
        return None

    total = len(labeled)
    counts: dict[str, int] = {}
    for pt in labeled:
        label = pt.label
        assert label is not None
        counts[label] = counts.get(label, 0) + 1

    return {code: round(p_area * cnt / total, 4) for code, cnt in counts.items()}


def coverage_with_ci(
    labels: list[str],
    confidence: float = 0.95,
) -> dict[str, dict]:
    """Per-code coverage % with Wilson confidence intervals.

    Returns:
        {"HC": {"pct": 42.3, "ci_lower": 38.1, "ci_upper": 46.7}, ...}
    """
    total = len(labels)
    if total == 0:
        return {}

    counts: dict[str, int] = {}
    for lbl in labels:
        counts[lbl] = counts.get(lbl, 0) + 1

    result = {}
    for code, cnt in counts.items():
        pct = round(cnt / total * 100, 2)
        ci_lo, ci_hi = wilson_confidence_interval(cnt, total, confidence)
        result[code] = {"pct": pct, "ci_lower": ci_lo, "ci_upper": ci_hi}
    return result


# ---------------------------------------------------------------------------
# Ecological indices — Fase 1 (Lapis 2)
# ---------------------------------------------------------------------------

def _codes_of_group(coral_groups: list[dict], group_name: str) -> set[str]:
    """Return the set of codes belonging to group_name (case-insensitive).

    Returns an empty set if the group is not found.
    """
    target = group_name.strip().lower()
    for g in coral_groups:
        if g.get("name", "").strip().lower() == target:
            return set(g.get("codes", []))
    return set()


def mortality_index(labels: list[str], coral_groups: list[dict]) -> Optional[float]:
    """Mortality Index (MI) = dead / (live_hard_coral + dead).

    dead            = count of points in group 'Dead Coral'
    live_hard_coral = count of points in group 'Hard Coral'
    Range 0..1; higher value = more coral mortality.
    Returns None when (live + dead) == 0 or neither group is found.
    """
    dead_codes = _codes_of_group(coral_groups, "Dead Coral")
    hc_codes = _codes_of_group(coral_groups, "Hard Coral")
    dead = sum(1 for lbl in labels if lbl in dead_codes)
    live = sum(1 for lbl in labels if lbl in hc_codes)
    denom = live + dead
    if denom == 0:
        return None
    return round(dead / denom, 4)


def reef_health_category(live_coral_pct: float) -> dict:
    """Classify reef health by Gomez & Yap (1988) / KepMen LH No.4/2001.

    Thresholds based on % live hard coral cover:
      [0, 25)   -> Buruk    (Poor)
      [25, 50)  -> Sedang   (Fair)
      [50, 75)  -> Baik     (Good)
      [75, 100] -> Sangat Baik (Excellent)

    Returns {'category': str, 'category_en': str, 'live_coral_pct': float}.
    """
    pct = live_coral_pct
    if pct < 25:
        cat, cat_en = "Buruk", "Poor"
    elif pct < 50:
        cat, cat_en = "Sedang", "Fair"
    elif pct < 75:
        cat, cat_en = "Baik", "Good"
    else:
        cat, cat_en = "Sangat Baik", "Excellent"
    return {"category": cat, "category_en": cat_en, "live_coral_pct": round(pct, 2)}


def coral_algae_ratio(labels: list[str], coral_groups: list[dict]) -> Optional[float]:
    """Coral-to-algae ratio = live_hard_coral_pct / algae_pct.

    >1 = coral-dominated (healthy); <1 = algae-dominated (phase shift risk).
    Returns None when algae_pct == 0 or either group is missing.
    """
    if not labels:
        return None
    total = len(labels)
    hc_codes = _codes_of_group(coral_groups, "Hard Coral")
    algae_codes = _codes_of_group(coral_groups, "Algae")
    hc_pct = sum(1 for lbl in labels if lbl in hc_codes) / total * 100
    algae_pct = sum(1 for lbl in labels if lbl in algae_codes) / total * 100
    if algae_pct == 0:
        return None
    return round(hc_pct / algae_pct, 4)


def berger_parker_dominance(labels: list[str]) -> float:
    """Berger-Parker dominance d = n_max / N.

    Proportion of the most abundant category. Range 0..1.
    Returns 0.0 when labels is empty.
    """
    if not labels:
        return 0.0
    counts: dict[str, int] = {}
    for lbl in labels:
        counts[lbl] = counts.get(lbl, 0) + 1
    return round(max(counts.values()) / len(labels), 4)


def hill_numbers(labels: list[str]) -> dict:
    """Hill numbers — effective number of species at three diversity orders.

    q0 = species richness (S)
    q1 = exp(Shannon H')          — exponential Shannon
    q2 = 1 / Simpson_D            — Simpson_D = sum(p_i^2)

    For a perfectly even community, q0 == q1 == q2 == S.
    Returns {'q0': int, 'q1': float, 'q2': float}.
    """
    if not labels:
        return {"q0": 0, "q1": 0.0, "q2": 0.0}
    counts: dict[str, int] = {}
    for lbl in labels:
        counts[lbl] = counts.get(lbl, 0) + 1
    N = len(labels)
    q0 = len(counts)
    H = -sum((c / N) * math.log(c / N) for c in counts.values())
    # Simpson concentration: sum of squared proportions
    D = sum((c / N) ** 2 for c in counts.values())
    q1 = round(math.exp(H), 4) if H > 0 else 1.0
    q2 = round(1 / D, 4) if D > 0 else float("inf")
    return {"q0": q0, "q1": q1, "q2": q2}
