import numpy as np
from src.models.project import ImageAnnotation, Project, Station
from src.core.analysis import (
    species_richness,
    pielou_evenness,
    margalef_richness,
    fisher_alpha,
    group_coverage,
    coverage_with_ci,
    cover_area_per_code,
    photo_area,
    mortality_index,
    reef_health_category,
    coral_algae_ratio,
    berger_parker_dominance,
    hill_numbers,
)


def image_coverage(annotation: ImageAnnotation) -> dict:
    """Percentage coverage per label for a single image."""
    return annotation.coverage_stats()


def project_summary(project: Project) -> dict:
    """
    Aggregate stats across all images in the project.

    Returns:
        {
            "coverage": {"HC": 45.2, ...},
            "coverage_ci": {"HC": {"pct": 45.2, "ci_lower": 40.1, "ci_upper": 50.4}, ...},
            "group_coverage": {"Hard Coral": 48.1, "Soft / Algae": 22.3, ...},
            "shannon_diversity": 1.23,
            "simpson_diversity": 0.75,
            "species_richness": 8,
            "pielou_evenness": 0.59,
            "margalef_richness": 1.82,
            "fisher_alpha": 2.41,
            "total_points": 200,
            "labeled_points": 198,
        }
    """
    return _summary_from_annotations(project.annotations, project.coral_groups)


def station_summary(station: Station, coral_groups: list | None = None) -> dict:
    """Aggregate stats scoped to a single station."""
    return _summary_from_annotations(station.annotations, coral_groups or [])


def per_image_table(project: Project) -> list[dict]:
    """Per-image stats for table display / export, with station column and CI columns."""
    rows = []
    for station in project.stations:
        for ann in station.annotations:
            stats = ann.coverage_stats()
            labels = [p.label for p in ann.points if p.label]
            ci_data = coverage_with_ci(labels)
            p_area = photo_area(ann)
            c_area = cover_area_per_code(ann)

            row: dict = {
                "station": station.name,
                "image": ann.image_path,
                "total_points": len(ann.points),
                "labeled_points": ann.labeled_count(),
            }
            if p_area is not None:
                row[f"photo_area_{ann.scale_unit}2"] = p_area

            # coverage %
            row.update(stats)

            # CI columns
            for code, info in ci_data.items():
                row[f"{code}_ci_lower"] = info["ci_lower"]
                row[f"{code}_ci_upper"] = info["ci_upper"]

            # cover area columns
            if c_area:
                for code, area in c_area.items():
                    row[f"{code}_area_{ann.scale_unit}2"] = area

            rows.append(row)
    return rows


def per_station_table(project: Project) -> list[dict]:
    """One row per station with aggregate coverage, diversity, and metadata."""
    rows = []
    for station in project.stations:
        counts: dict[str, int] = {}
        labels: list[str] = []
        total_photo_area = 0.0
        has_area = False

        for ann in station.annotations:
            for p in ann.points:
                if p.label:
                    counts[p.label] = counts.get(p.label, 0) + 1
                    labels.append(p.label)
            p_area = photo_area(ann)
            if p_area is not None:
                total_photo_area += p_area
                has_area = True

        total_labeled = sum(counts.values())
        N = total_labeled
        S = species_richness(labels)
        H = _shannon_index(list(counts.values()), N) if N else 0.0
        simpson = _simpson_index(list(counts.values()), N) if N else 0.0

        row: dict = {
            "station": station.name,
            "depth_m": station.depth_m,
            "date": station.date,
            "gps_lat": station.gps_lat,
            "gps_lon": station.gps_lon,
            "total_points": station.total_points(),
            "labeled_points": station.labeled_points(),
            "species_richness": S,
            "shannon_H": round(H, 4),
            "simpson_1D": round(simpson, 4),
            "pielou_J": round(pielou_evenness(H, S), 4),
            "margalef_d": round(margalef_richness(S, N), 4),
        }
        if has_area:
            # use scale_unit of first annotation
            unit = station.annotations[0].scale_unit if station.annotations else "cm"
            row[f"total_photo_area_{unit}2"] = round(total_photo_area, 4)

        if total_labeled:
            row.update({k: round(v / total_labeled * 100, 2) for k, v in counts.items()})

        # Group coverage
        coral_groups_list = project.coral_groups if hasattr(project, "coral_groups") else []
        grp_cov = group_coverage(labels, coral_groups_list)
        for grp, pct in grp_cov.items():
            row[f"group_{grp}"] = pct

        # Ecological indices (Lapis 2)
        live_coral_pct = grp_cov.get("Hard Coral", 0.0)
        mi = mortality_index(labels, coral_groups_list)
        health = reef_health_category(live_coral_pct)
        row["mortality_index"] = mi
        row["reef_health_category"] = health["category"]
        row["coral_algae_ratio"] = coral_algae_ratio(labels, coral_groups_list)
        row["berger_parker"] = berger_parker_dominance(labels)
        hill = hill_numbers(labels)
        row["hill_q0"] = hill["q0"]
        row["hill_q1"] = hill["q1"]
        row["hill_q2"] = hill["q2"]

        rows.append(row)
    return rows


def _summary_from_annotations(
    annotations: list[ImageAnnotation],
    coral_groups: list | None = None,
) -> dict:
    all_labels: list[str] = []
    for ann in annotations:
        for point in ann.points:
            if point.label:
                all_labels.append(point.label)

    if not all_labels:
        return {}

    total = len(all_labels)
    counts: dict[str, int] = {}
    for label in all_labels:
        counts[label] = counts.get(label, 0) + 1

    coverage = {k: round(v / total * 100, 2) for k, v in counts.items()}
    H = _shannon_index(list(counts.values()), total)
    simpson = _simpson_index(list(counts.values()), total)
    S = species_richness(all_labels)
    J = pielou_evenness(H, S)
    d = margalef_richness(S, total)
    alpha = fisher_alpha(S, total)

    total_points = sum(len(a.points) for a in annotations)
    labeled_points = sum(a.labeled_count() for a in annotations)

    ci_data = coverage_with_ci(all_labels)
    grp_cov = group_coverage(all_labels, coral_groups or [])

    live_coral_pct = grp_cov.get("Hard Coral", 0.0)
    mi = mortality_index(all_labels, coral_groups or [])
    health = reef_health_category(live_coral_pct)
    car = coral_algae_ratio(all_labels, coral_groups or [])
    bp = berger_parker_dominance(all_labels)
    hill = hill_numbers(all_labels)

    return {
        "coverage": coverage,
        "coverage_ci": ci_data,
        "group_coverage": grp_cov,
        "shannon_diversity": round(H, 4),
        "simpson_diversity": round(simpson, 4),
        "species_richness": S,
        "pielou_evenness": round(J, 4),
        "margalef_richness": round(d, 4),
        "fisher_alpha": round(alpha, 4),
        "total_points": total_points,
        "labeled_points": labeled_points,
        "mortality_index": mi,
        "reef_health": health,
        "coral_algae_ratio": car,
        "berger_parker": bp,
        "hill": hill,
    }


def _shannon_index(counts: list[int], total: int) -> float:
    """Shannon-Weaver diversity index H'."""
    h = 0.0
    for c in counts:
        if c > 0:
            p = c / total
            h -= p * np.log(p)
    return h


def _simpson_index(counts: list[int], total: int) -> float:
    """Simpson's diversity index (1 - D)."""
    d = sum(c * (c - 1) for c in counts)
    n = total * (total - 1)
    return 1 - (d / n) if n > 0 else 0.0
