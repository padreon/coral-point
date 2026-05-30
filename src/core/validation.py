"""Validation guards for advanced (Lapis 3) analyses.

Every function returns a ValidationResult (never raises) so callers can
display human-readable reasons when prerequisites are not met.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class ValidationResult:
    """Result of a prerequisite validation check."""

    ok: bool
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_metadata_completeness(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    project: object,
) -> dict[str, ValidationResult]:
    """Check per-analysis metadata prerequisites.

    Keys returned: 'temporal', 'spatial', 'area', 'depth'.
    Each value is a ValidationResult explaining which stations are missing data.
    Never raises even when all metadata is absent.
    """
    stations = getattr(project, "stations", [])
    annotations = getattr(project, "annotations", [])

    # --- temporal: >=2 stations with distinct valid ISO-8601 dates ---
    temporal_ok = False
    temporal_reasons: list[str] = []
    valid_dates: set[str] = set()
    missing_date: list[str] = []
    for st in stations:
        d = getattr(st, "date", None)
        if d:
            try:
                date.fromisoformat(str(d))
                valid_dates.add(str(d))
            except ValueError:
                missing_date.append(f"{st.name} (invalid date: {d!r})")
        else:
            missing_date.append(f"{st.name} (no date)")
    if len(valid_dates) >= 2:
        temporal_ok = True
    else:
        if missing_date:
            temporal_reasons.append("Missing/invalid date on: " + ", ".join(missing_date))
        temporal_reasons.append(
            f"Need >=2 stations with distinct dates; found {len(valid_dates)} unique date(s)."
        )

    # --- spatial: >=3 stations with valid GPS lat/lon (not None, not 0) ---
    spatial_ok = False
    spatial_reasons: list[str] = []
    missing_gps: list[str] = []
    valid_gps_count = 0
    for st in stations:
        lat = getattr(st, "gps_lat", None)
        lon = getattr(st, "gps_lon", None)
        if lat and lon and float(lat) != 0.0 and float(lon) != 0.0:
            valid_gps_count += 1
        else:
            missing_gps.append(st.name)
    if valid_gps_count >= 3:
        spatial_ok = True
    else:
        if missing_gps:
            spatial_reasons.append("Missing GPS on: " + ", ".join(missing_gps))
        spatial_reasons.append(
            f"Need >=3 stations with GPS; found {valid_gps_count}."
        )

    # --- area: >=1 annotation with scale_factor calibrated (!=1.0 and !=0) ---
    area_ok = False
    area_reasons: list[str] = []
    calibrated = sum(
        1 for ann in annotations
        if getattr(ann, "scale_factor", 1.0) not in (0.0, 1.0)
    )
    if calibrated >= 1:
        area_ok = True
    else:
        area_reasons.append("No calibrated images found (scale_factor == 1.0 or 0 for all images).")

    # --- depth: >=3 stations with depth_m > 0 ---
    depth_ok = False
    depth_reasons: list[str] = []
    missing_depth: list[str] = []
    valid_depth_count = 0
    for st in stations:
        dm = getattr(st, "depth_m", None)
        if dm is not None and float(dm) > 0:
            valid_depth_count += 1
        else:
            missing_depth.append(st.name)
    if valid_depth_count >= 3:
        depth_ok = True
    else:
        if missing_depth:
            depth_reasons.append("Missing depth on: " + ", ".join(missing_depth))
        depth_reasons.append(
            f"Need >=3 stations with depth_m > 0; found {valid_depth_count}."
        )

    return {
        "temporal": ValidationResult(ok=temporal_ok, reasons=temporal_reasons),
        "spatial": ValidationResult(ok=spatial_ok, reasons=spatial_reasons),
        "area": ValidationResult(ok=area_ok, reasons=area_reasons),
        "depth": ValidationResult(ok=depth_ok, reasons=depth_reasons),
    }


def validate_sampling_consistency(project: object) -> ValidationResult:
    """Check that all images use the same point distribution and similar point counts.

    ok=True when:
    - All labeled images use the same point_distribution (from project), AND
    - Ratio of max/min labeled-point counts across images <= 2.0.

    Warnings are added for images with <25 labeled points.
    Never raises.
    """
    stations = getattr(project, "stations", [])
    point_distribution = getattr(project, "point_distribution", None)
    reasons: list[str] = []
    warnings: list[str] = []

    labeled_counts: list[int] = []
    for st in stations:
        for ann in getattr(st, "annotations", []):
            labeled = sum(1 for p in getattr(ann, "points", []) if getattr(p, "label", None))
            labeled_counts.append(labeled)
            if 0 < labeled < 25:
                warnings.append(
                    f"{ann.image_path}: only {labeled} labeled points (< 25, less reliable)."
                )

    nonempty = [c for c in labeled_counts if c > 0]
    if len(nonempty) >= 2:
        ratio = max(nonempty) / min(nonempty)
        if ratio > 2.0:
            reasons.append(
                f"Labeled point counts vary too much across images "
                f"(max/min ratio = {ratio:.1f}, threshold = 2.0). "
                "Proportional comparisons may be unreliable."
            )

    # point_distribution consistency: since all images share the project-level setting,
    # the only source of inconsistency is if the project value is missing/unknown.
    if not point_distribution:
        reasons.append("point_distribution not set on project.")

    ok = len(reasons) == 0
    return ValidationResult(ok=ok, reasons=reasons, warnings=warnings)


def can_run_multivariate(project: object) -> ValidationResult:
    """Gate for multivariate analyses (Bray-Curtis, nMDS, PERMANOVA, SIMPER).

    ok=True when ALL of:
    - Number of stations >= 4
    - validate_sampling_consistency(project).ok == True

    Returns specific, actionable reasons when conditions are not met.
    """
    stations = getattr(project, "stations", [])
    reasons: list[str] = []
    warnings: list[str] = []

    n_stations = len(stations)
    if n_stations < 4:
        reasons.append(
            f"Need at least 4 stations for multivariate analysis; project has {n_stations}."
        )

    consistency = validate_sampling_consistency(project)
    if not consistency.ok:
        reasons.extend(consistency.reasons)
    warnings.extend(consistency.warnings)

    return ValidationResult(ok=len(reasons) == 0, reasons=reasons, warnings=warnings)
