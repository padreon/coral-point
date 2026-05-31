"""Generate a dummy coralX project (.cpce) for testing charts and analysis.

Configuration: 10 stations, 50 images/station, 30 points/image = 15,000 points total.
Run from repo root: python tools/generate_dummy.py
"""

import json
import math
import random
import sys
from pathlib import Path

SEED = 42
N_STATIONS = 10
N_IMAGES_PER_STATION = 50
N_POINTS_PER_IMAGE = 30
IMAGE_W, IMAGE_H = 1920, 1080
OUTPUT = Path("data/dummy_project.cpce")

# Realistic station locations (Bunaken area, North Sulawesi)
BASE_LAT = -1.615
BASE_LON = 124.760

DEPTHS = [3.0, 5.0, 7.0, 10.0, 12.0, 15.0, 18.0, 8.0, 6.0, 20.0]
DATES = [
    "2024-03-10", "2024-03-11", "2024-03-12", "2024-03-13", "2024-03-14",
    "2024-03-15", "2024-03-16", "2024-03-17", "2024-03-18", "2024-03-19",
]


def load_codes(json_path: str) -> tuple[dict, list]:
    with open(json_path) as f:
        data = json.load(f)
    return data["codes"], data["groups"]


def make_label_weights(groups: list[dict]) -> dict[str, float]:
    """Assign realistic sampling weights per code (mimics healthy reef)."""
    weights: dict[str, float] = {}
    group_base = {
        "Hard Coral":          0.38,
        "Dead Coral":          0.08,
        "Soft Coral & Biota":  0.10,
        "Algae":               0.18,
        "Substrate":           0.22,
        "Non-biological":      0.04,
    }
    for g in groups:
        n = len(g["codes"])
        if n == 0:
            continue
        base = group_base.get(g["name"], 0.05)
        for code in g["codes"]:
            weights[code] = base / n
    return weights


def weighted_choice(codes: list[str], weights: dict[str, float], rng: random.Random) -> str:
    total = sum(weights.get(c, 0.01) for c in codes)
    r = rng.uniform(0, total)
    cumul = 0.0
    for c in codes:
        cumul += weights.get(c, 0.01)
        if r <= cumul:
            return c
    return codes[-1]


def build_project(codes: dict, groups: list) -> dict:
    rng = random.Random(SEED)
    code_list = list(codes.keys())
    label_weights = make_label_weights(groups)

    # Per-station group label: vary coverage slightly per station
    stations = []
    for si in range(N_STATIONS):
        st_name = f"Station-{si+1:02d}"
        st_lat = BASE_LAT + rng.uniform(-0.05, 0.05)
        st_lon = BASE_LON + rng.uniform(-0.05, 0.05)

        # Vary health per station (some stations healthier than others)
        hc_boost = rng.uniform(0.7, 1.4)
        st_weights = {c: w * (hc_boost if any(c in g["codes"] and g["name"] == "Hard Coral"
                                               for g in groups) else 1.0)
                      for c, w in label_weights.items()}

        annotations = []
        for ai in range(N_IMAGES_PER_STATION):
            points = []
            for pi in range(N_POINTS_PER_IMAGE):
                x = rng.uniform(50, IMAGE_W - 50)
                y = rng.uniform(50, IMAGE_H - 50)
                label = weighted_choice(code_list, st_weights, rng)
                # look up category (group name) for this label
                category = next(
                    (g["name"] for g in groups if label in g["codes"]), ""
                )
                points.append({
                    "x": round(x, 1),
                    "y": round(y, 1),
                    "index": pi,
                    "label": label,
                    "category": category,
                })

            annotations.append({
                "image_path": f"/dummy/images/{st_name}/img_{ai+1:03d}.jpg",
                "image_width": IMAGE_W,
                "image_height": IMAGE_H,
                "scale_factor": 1.0,
                "scale_unit": "cm",
                "points": points,
            })

        stations.append({
            "name": st_name,
            "depth_m": DEPTHS[si],
            "date": DATES[si],
            "gps_lat": round(st_lat, 6),
            "gps_lon": round(st_lon, 6),
            "notes": f"Dummy station {si+1}",
            "annotations": annotations,
        })

    return {
        "name": "Dummy Project — 10 Stations",
        "point_count": N_POINTS_PER_IMAGE,
        "point_distribution": "random",
        "border_exclusion": 0,
        "border_rect": None,
        "border_polygon": None,
        "coral_codes": codes,
        "coral_groups": groups,
        "stations": stations,
        "save_path": str(OUTPUT.resolve()),
    }


def main():
    codes_path = Path("data/coral_codes_default.json")
    if not codes_path.exists():
        print(f"ERROR: {codes_path} not found. Run from repo root.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading codes from {codes_path}...")
    codes, groups = load_codes(str(codes_path))
    print(f"  {len(codes)} codes, {len(groups)} groups")

    print(f"Generating {N_STATIONS} stations × {N_IMAGES_PER_STATION} images × "
          f"{N_POINTS_PER_IMAGE} points = "
          f"{N_STATIONS * N_IMAGES_PER_STATION * N_POINTS_PER_IMAGE:,} points...")
    project = build_project(codes, groups)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False)

    size_kb = OUTPUT.stat().st_size / 1024
    print(f"Saved → {OUTPUT}  ({size_kb:.0f} KB)")
    print("Done. Open this file in coralX via File → Open Project.")


if __name__ == "__main__":
    main()
