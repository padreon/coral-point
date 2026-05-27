"""Import functions: coral codes, station metadata, labeled points, CPCe Excel/CPC."""

from __future__ import annotations

import csv
import io
import json
import os
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from src.models.project import ImageAnnotation, Point, Project, Station


# ─────────────────────────────────────────────────────────────
# Return types
# ─────────────────────────────────────────────────────────────

@dataclass
class ImportResult:
    """Summary returned by every import function."""
    success: bool
    message: str
    warnings: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# 1. Import coral codes from JSON or CSV
# ─────────────────────────────────────────────────────────────

def _parse_cpce_field_line(line: str) -> tuple[str, str, str] | None:
    """
    Parse one data line from a CPCe code file.

    CPCe files use spaces after commas (', ') which confuses the default CSV
    reader — fields like ' "Tape, wand, shadow"' would not be unquoted.
    skipinitialspace=True tells the reader to skip whitespace before each field,
    so the opening quote is recognized and the comma inside is part of the value.

      "CODE", "Description", HEXCOLOR      → (code, desc, hex_color)
      "CODE", "Description", "PARENT_CODE" → (code, desc, parent_code)

    Returns None if the line cannot be parsed as a valid code entry.
    """
    line = line.strip()
    if not line or line.upper().startswith("NOTES"):
        return None
    try:
        reader = csv.reader(io.StringIO(line), skipinitialspace=True)
        fields = [f.strip() for f in next(reader)]
    except Exception:
        return None

    if len(fields) < 2:
        return None

    code = fields[0].strip().strip('"')   # remove stray quotes from code
    desc = fields[1].strip() if len(fields) > 1 else ""
    third = fields[2].strip() if len(fields) > 2 else ""

    if not code:
        return None
    return code, desc, third


def _is_hex_color(s: str) -> bool:
    """Return True if s is a 6-character hex color string (no # prefix)."""
    s = s.strip()
    if len(s) != 6:
        return False
    try:
        int(s, 16)
        return True
    except ValueError:
        return False


def _parse_cpce_code_txt(content: str) -> tuple[dict[str, str], list[dict], list[str]]:
    """
    Parse a CPCe coral code .txt file.

    Format:
      Line 0 : background color (hex, ignored)
      Line 1 : selection color (hex, ignored)
      Line 2 : number of top-level categories N
      Lines 3…3+N-1 : category definitions  → "CODE","Desc",HEXCOLOR
      Lines 3+N…NOTES : sub-code definitions → "CODE","Desc","PARENT_CODE"
      NOTES,NOTES,NOTES separator
      Lines after NOTES : species/notes codes → "CODE","Desc","PARENT_CODE" (or "NA")

    Returns (codes_dict, groups_list, warnings_list).
    groups_list entries include an optional "color" key (6-char hex from the file).
    """
    raw_lines = [ln.rstrip() for ln in content.splitlines()]
    # Strip blank lines at top
    lines = [ln for ln in raw_lines if ln.strip()]

    warnings: list[str] = []
    codes: dict[str, str] = {}
    groups: list[dict] = []

    if len(lines) < 3:
        raise ValueError("File too short to be a CPCe code file.")

    # Line 2: number of categories
    try:
        n_cats = int(lines[2].strip())
    except ValueError:
        raise ValueError(f"Expected integer on line 3, got: '{lines[2]}'")

    # ── Parse top-level categories ─────────────────────────────────────────
    # category_code → {description, color}
    category_map: dict[str, dict] = {}
    for i in range(3, min(3 + n_cats, len(lines))):
        parsed = _parse_cpce_field_line(lines[i])
        if not parsed:
            warnings.append(f"Could not parse category line {i+1}: '{lines[i]}'")
            continue
        cat_code, cat_desc, third = parsed
        color = third if _is_hex_color(third) else ""
        category_map[cat_code] = {"description": cat_desc, "color": color}
        codes[cat_code] = cat_desc  # category codes are also valid labeling codes

    # ── Parse sub-codes and notes codes ───────────────────────────────────
    group_members: dict[str, list[str]] = {k: [] for k in category_map}

    for i in range(3 + n_cats, len(lines)):
        line = lines[i].strip()
        if not line:
            continue
        if line.upper().startswith("NOTES"):
            continue

        parsed = _parse_cpce_field_line(line)
        if not parsed:
            continue

        code, desc, parent = parsed

        # Skip if the "code" looks like a hex color (malformed line)
        if _is_hex_color(code):
            continue

        codes[code] = desc

        # Assign to group if parent matches a category
        if parent in category_map:
            group_members.setdefault(parent, [])
            if code not in group_members[parent]:
                group_members[parent].append(code)
        elif parent and parent not in ("NA", "N/A", ""):
            # Parent not in categories — could be a sub-category reference
            # (e.g. "AC" in COREMAP is not a category itself)
            warnings.append(f"Code '{code}' has unknown parent '{parent}' — added ungrouped.")

    # ── Build groups ───────────────────────────────────────────────────────
    for cat_code, cat_info in category_map.items():
        members = group_members.get(cat_code, [])
        entry: dict = {
            "name": cat_info["description"],
            "codes": members,
        }
        if cat_info["color"]:
            entry["color"] = cat_info["color"]
        groups.append(entry)

    return codes, groups, warnings


def import_coral_codes(path: str) -> tuple[dict[str, str], list[dict], ImportResult]:
    """
    Read coral codes (and optionally groups) from a JSON, CSV, or CPCe .txt file.

    CPCe .txt format (from the original CPCe Visual Basic software):
      Line 1: bg color, Line 2: sel color, Line 3: N categories,
      then N category lines ("CODE","Desc",HEXCOLOR), then sub-code lines
      ("CODE","Desc","PARENT"), NOTES separator, species-level codes.

    JSON formats accepted:
      • {"HC": "Hard Coral", "SC": "Soft Coral"}
      • {"codes": {"HC": "Hard Coral"}, "groups": [{"name": "Hard Coral", "codes": ["HC"]}]}
      • [{"code": "HC", "description": "Hard Coral"}, ...]

    CSV format (must have header row):
      • columns: code, description  (+ optional group)

    Returns (codes_dict, groups_list, result).
    Groups include an optional "color" key (6-char hex) when parsed from CPCe .txt.
    """
    ext = os.path.splitext(path)[1].lower()
    codes: dict[str, str] = {}
    groups: list[dict] = []
    warnings: list[str] = []

    try:
        if ext == ".json":
            with open(path) as f:
                data = json.load(f)

            if isinstance(data, dict):
                if "codes" in data:
                    # Our own export format — preserve case exactly as written
                    raw = data["codes"]
                    groups = data.get("groups", [])
                else:
                    raw = data
                if isinstance(raw, dict):
                    codes = {str(k): str(v) for k, v in raw.items()}
                else:
                    return {}, [], ImportResult(False, f"Unexpected JSON structure in {path}")
            elif isinstance(data, list):
                for item in data:
                    code = str(item.get("code", "")).upper()
                    desc = str(item.get("description", ""))
                    if code:
                        codes[code] = desc
            else:
                return {}, [], ImportResult(False, f"Unexpected JSON root type in {path}")

        elif ext == ".txt":
            with open(path, encoding="utf-8", errors="replace") as f:
                content = f.read()
            codes, groups, warnings = _parse_cpce_code_txt(content)

        elif ext in (".csv", ".tsv"):
            sep = "\t" if ext == ".tsv" else ","
            df = pd.read_csv(path, sep=sep, dtype=str).fillna("")
            df.columns = [c.strip().lower() for c in df.columns]

            code_col = next((c for c in df.columns if c in ("code", "kode")), None)
            desc_col = next((c for c in df.columns if c in ("description", "desc", "deskripsi", "name")), None)
            group_col = next((c for c in df.columns if c in ("group", "grup", "category")), None)

            if code_col is None:
                return {}, [], ImportResult(False, "CSV must have a 'code' column.")

            group_map: dict[str, list[str]] = {}
            for _, row in df.iterrows():
                code = str(row[code_col]).strip().upper()
                if not code:
                    continue
                desc = str(row[desc_col]).strip() if desc_col else ""
                codes[code] = desc
                if group_col:
                    grp = str(row[group_col]).strip()
                    if grp:
                        group_map.setdefault(grp, []).append(code)

            if group_map:
                groups = [{"name": g, "codes": cs} for g, cs in group_map.items()]

        else:
            return {}, [], ImportResult(False, f"Unsupported file type: {ext}. Use .txt, .json, or .csv")

    except Exception as exc:
        return {}, [], ImportResult(False, f"Failed to read file: {exc}")

    if not codes:
        return {}, [], ImportResult(False, "No codes found in file.")

    return codes, groups, ImportResult(
        True,
        f"Loaded {len(codes)} code(s)" + (f" and {len(groups)} group(s)" if groups else ""),
        warnings,
    )


# ─────────────────────────────────────────────────────────────
# 2. Import station metadata from CSV
# ─────────────────────────────────────────────────────────────

_STATION_COL_ALIASES = {
    "station": ("station", "station_name", "nama_stasiun", "site", "transect"),
    "depth_m": ("depth_m", "depth", "kedalaman", "kedalaman_m"),
    "date": ("date", "tanggal", "survey_date"),
    "gps_lat": ("gps_lat", "lat", "latitude", "lintang"),
    "gps_lon": ("gps_lon", "lon", "longitude", "bujur"),
    "notes": ("notes", "catatan", "remarks", "note"),
}


def _find_col(columns: list[str], aliases: tuple[str, ...]) -> Optional[str]:
    for alias in aliases:
        if alias in columns:
            return alias
    return None


def import_station_metadata(path: str) -> tuple[list[dict], ImportResult]:
    """
    Read station metadata from a CSV file.

    Required column: station (or station_name / site / transect)
    Optional columns: depth_m, date (ISO-8601), gps_lat, gps_lon, notes

    Returns (list_of_station_dicts, result).
    Each dict has keys: name, depth_m, date, gps_lat, gps_lon, notes.
    """
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
        df.columns = [c.strip().lower() for c in df.columns]
    except Exception as exc:
        return [], ImportResult(False, f"Cannot read CSV: {exc}")

    cols = list(df.columns)
    mapping = {field: _find_col(cols, aliases) for field, aliases in _STATION_COL_ALIASES.items()}

    if mapping["station"] is None:
        return [], ImportResult(False,
            "CSV must have a station name column (e.g. 'station', 'site', or 'transect').")

    stations: list[dict] = []
    warnings: list[str] = []

    for _, row in df.iterrows():
        name = str(row[mapping["station"]]).strip()
        if not name:
            continue

        def _float(col_key: str) -> Optional[float]:
            col = mapping[col_key]
            if col is None:
                return None
            val = str(row[col]).strip()
            try:
                return float(val) if val else None
            except ValueError:
                warnings.append(f"Station '{name}': invalid {col_key} value '{val}'")
                return None

        def _str(col_key: str) -> str:
            col = mapping[col_key]
            return str(row[col]).strip() if col else ""

        stations.append({
            "name": name,
            "depth_m": _float("depth_m"),
            "date": _str("date") or None,
            "gps_lat": _float("gps_lat"),
            "gps_lon": _float("gps_lon"),
            "notes": _str("notes"),
        })

    if not stations:
        return [], ImportResult(False, "No station rows found in CSV.")

    return stations, ImportResult(
        True, f"Read {len(stations)} station(s).", warnings
    )


# ─────────────────────────────────────────────────────────────
# 3. Import labeled points from CSV/Excel (coralX export format)
# ─────────────────────────────────────────────────────────────

def import_labeled_points(path: str, project: Project) -> ImportResult:
    """
    Read labeled point data from a CSV or Excel file and apply labels to
    annotations already present in the project.

    Accepted formats
    ────────────────
    A) Raw Points sheet / CSV  — columns: image, point_index, label
       (station is optional; x/y/category are ignored but accepted)

    B) CPCe-style per-image table — columns: image (or frame), then one column
       per code with % values.  Only coverage percentages, no per-point import.
       In this case the function returns a warning that per-point data is needed.

    The image column is matched by basename (filename without directory path)
    against annotations already in the project.

    Returns ImportResult with counts.
    """
    ext = os.path.splitext(path)[1].lower()
    warnings: list[str] = []

    try:
        if ext in (".xlsx", ".xls"):
            # Try "Raw Points" sheet first, fall back to first sheet
            xf = pd.ExcelFile(path)
            sheet = "Raw Points" if "Raw Points" in xf.sheet_names else xf.sheet_names[0]
            df = pd.read_excel(path, sheet_name=sheet, dtype=str).fillna("")
        elif ext == ".csv":
            df = pd.read_csv(path, dtype=str).fillna("")
        else:
            return ImportResult(False, f"Unsupported file type: {ext}. Use .csv or .xlsx")
    except Exception as exc:
        return ImportResult(False, f"Cannot read file: {exc}")

    df.columns = [c.strip().lower() for c in df.columns]

    image_col = next((c for c in df.columns if c in ("image", "gambar", "frame", "filename", "file")), None)
    idx_col   = next((c for c in df.columns if c in ("point_index", "point", "index", "no", "#")), None)
    label_col = next((c for c in df.columns if c in ("label", "code", "kode", "species", "substrate")), None)
    cat_col   = next((c for c in df.columns if c in ("category", "group", "kategori")), None)

    if image_col is None or label_col is None:
        return ImportResult(False,
            "File must have columns: 'image' (or 'frame') and 'label' (or 'code').")

    # Build lookup: basename → annotation
    ann_map: dict[str, ImageAnnotation] = {}
    for ann in project.annotations:
        ann_map[os.path.basename(ann.image_path).lower()] = ann

    matched = 0
    skipped_images: set[str] = set()
    updated_labels = 0

    for _, row in df.iterrows():
        img_raw = str(row[image_col]).strip()
        img_key = os.path.basename(img_raw).lower()
        label = str(row[label_col]).strip().upper()

        if not img_key or not label:
            continue

        ann = ann_map.get(img_key)
        if ann is None:
            skipped_images.add(img_key)
            continue

        matched += 1

        # Resolve point by index if available, otherwise by order
        if idx_col:
            try:
                idx = int(str(row[idx_col]).strip())
            except ValueError:
                idx = -1
            pts = [p for p in ann.points if p.index == idx]
            pt = pts[0] if pts else None
        else:
            # No index column — apply in order
            unlabeled = [p for p in ann.points if not p.label]
            pt = unlabeled[0] if unlabeled else None

        if pt is None:
            warnings.append(f"{img_key}: no matching point for row (label={label})")
            continue

        pt.label = label
        if cat_col:
            pt.category = str(row[cat_col]).strip() or None
        updated_labels += 1

    if skipped_images:
        warnings.append(
            f"{len(skipped_images)} image(s) not found in project: "
            + ", ".join(sorted(skipped_images)[:5])
            + ("…" if len(skipped_images) > 5 else "")
        )

    if updated_labels == 0 and not warnings:
        return ImportResult(False, "No labels were applied. Check that images are added to the project first.")

    return ImportResult(
        True,
        f"Applied {updated_labels} label(s) across {matched} row(s).",
        warnings,
    )


# ─────────────────────────────────────────────────────────────
# 4. Import from old CPCe Excel export
# ─────────────────────────────────────────────────────────────

# Known CPCe column name variants
_CPCE_CODE_COLS = ("code", "substrate", "species", "label", "kode")
_CPCE_X_COLS    = ("x", "x_coord", "x coordinate", "col", "column")
_CPCE_Y_COLS    = ("y", "y_coord", "y coordinate", "row")
_CPCE_IDX_COLS  = ("point", "point #", "point#", "#", "no", "index", "point_index")
_CPCE_IMG_COLS  = ("image", "frame", "image name", "filename", "file", "photo")


def import_cpce_excel(path: str) -> tuple[Optional[Project], ImportResult]:
    """
    Import an Excel file exported by the original CPCe (Visual Basic) software.

    Strategy
    ────────
    1. Try to read a sheet named "Raw Points", "Data", or the first sheet.
    2. Detect column mapping by checking known CPCe column name variants.
    3. If columns found → create a Project with one Station per unique station
       value (or a single Station if no station column).
    4. For each unique image value → create an ImageAnnotation with Points.
    5. If columns NOT found (summary-only export) → return a descriptive error.

    Multi-sheet CPCe exports (one sheet per image frame) are also handled:
    each sheet becomes one ImageAnnotation; sheet name is used as image name.
    """
    warnings: list[str] = []

    try:
        xf = pd.ExcelFile(path)
    except Exception as exc:
        return None, ImportResult(False, f"Cannot open Excel file: {exc}")

    preferred_sheets = ["Raw Points", "Data", "Points", "Titik"]
    target_sheet = next((s for s in preferred_sheets if s in xf.sheet_names), None)

    if target_sheet:
        frames = {target_sheet: pd.read_excel(path, sheet_name=target_sheet, dtype=str).fillna("")}
    else:
        # Load all sheets — will try each
        frames = {s: pd.read_excel(path, sheet_name=s, dtype=str).fillna("")
                  for s in xf.sheet_names}

    def _detect_cols(df: pd.DataFrame) -> dict:
        cols = [c.strip().lower() for c in df.columns]
        df.columns = cols
        return {
            "code":    next((c for c in cols if c in _CPCE_CODE_COLS), None),
            "x":       next((c for c in cols if c in _CPCE_X_COLS), None),
            "y":       next((c for c in cols if c in _CPCE_Y_COLS), None),
            "idx":     next((c for c in cols if c in _CPCE_IDX_COLS), None),
            "image":   next((c for c in cols if c in _CPCE_IMG_COLS), None),
            "station": next((c for c in cols if c in ("station", "transect", "site", "stasiun")), None),
        }

    project = Project(name=os.path.splitext(os.path.basename(path))[0])
    station_map: dict[str, Station] = {}
    total_points = 0

    # ── Multi-sheet mode: one annotation per sheet ──────────────
    if len(frames) > 1 or target_sheet is None:
        default_station = Station(name="Imported Station")

        for sheet_name, df in frames.items():
            if df.empty or len(df.columns) < 2:
                continue
            mapping = _detect_cols(df)
            if mapping["code"] is None:
                warnings.append(f"Sheet '{sheet_name}': no code column found, skipped.")
                continue

            ann = ImageAnnotation(image_path=sheet_name)
            for i, (_, row) in enumerate(df.iterrows()):
                code = str(row[mapping["code"]]).strip().upper()
                if not code or code in ("CODE", "KODE", ""):
                    continue
                try:
                    x = float(row[mapping["x"]]) if mapping["x"] else float(i)
                    y = float(row[mapping["y"]]) if mapping["y"] else 0.0
                except (ValueError, TypeError):
                    x, y = float(i), 0.0
                idx = i
                if mapping["idx"]:
                    try:
                        idx = int(str(row[mapping["idx"]]).strip())
                    except ValueError:
                        pass
                pt = Point(x=x, y=y, index=idx, label=code)
                ann.points.append(pt)
                total_points += 1

            if ann.points:
                default_station.annotations.append(ann)

        if default_station.annotations:
            project.stations.append(default_station)

    # ── Single-sheet mode: image column groups rows ──────────────
    else:
        sheet_name, df = next(iter(frames.items()))
        mapping = _detect_cols(df)

        if mapping["code"] is None:
            return None, ImportResult(False,
                "No code/species column found. "
                "Expected columns like 'code', 'substrate', or 'species'.\n"
                f"Found: {list(df.columns)}")

        for i, (_, row) in enumerate(df.iterrows()):
            code = str(row[mapping["code"]]).strip().upper()
            if not code or code in ("CODE", "KODE", "SUBSTRATE", "SPECIES"):
                continue

            img_name = str(row[mapping["image"]]).strip() if mapping["image"] else "image_1"
            st_name  = str(row[mapping["station"]]).strip() if mapping["station"] else "Imported Station"

            if st_name not in station_map:
                st = Station(name=st_name)
                station_map[st_name] = st
                project.stations.append(st)
            station = station_map[st_name]

            ann_map: dict[str, ImageAnnotation] = {
                os.path.basename(a.image_path).lower(): a
                for a in station.annotations
            }
            img_key = os.path.basename(img_name).lower()
            if img_key not in ann_map:
                ann = ImageAnnotation(image_path=img_name)
                station.annotations.append(ann)
                ann_map[img_key] = ann
            ann = ann_map[img_key]

            try:
                x = float(row[mapping["x"]]) if mapping["x"] else float(i)
                y = float(row[mapping["y"]]) if mapping["y"] else 0.0
            except (ValueError, TypeError):
                x, y = float(i), 0.0

            idx = len(ann.points)
            if mapping["idx"]:
                try:
                    idx = int(str(row[mapping["idx"]]).strip())
                except ValueError:
                    pass

            ann.points.append(Point(x=x, y=y, index=idx, label=code))
            total_points += 1

    if total_points == 0:
        return None, ImportResult(False,
            "No point data found in the file. "
            "Make sure the file contains per-point rows (not just summary stats).",
            warnings)

    n_stations  = len(project.stations)
    n_images    = sum(len(s.annotations) for s in project.stations)
    return project, ImportResult(
        True,
        f"Imported {total_points} points across {n_images} image(s) in {n_stations} station(s).",
        warnings,
    )


# ─────────────────────────────────────────────────────────────
# 5. Import CPCe native .cpc annotation file
# ─────────────────────────────────────────────────────────────

def import_cpce_cpc(
    path: str,
    image_dir: Optional[str] = None,
) -> tuple[Optional[ImageAnnotation], ImportResult]:
    """
    Import a single CPCe native .cpc annotation file.

    .cpc format (CPCe Visual Basic 6.0 save format):
      Line 1 : "code_file","image_file",int_width,int_height,disp_w,disp_h
      Lines 2–5 : 4 border rectangle corners in CPCe twips (x,y each)
      Line 6 : N — number of annotation points
      Lines 7..6+N : point coordinates in CPCe twips, one "x,y" per line
      Lines 7+N..6+2N : labeled points — "index","code","Notes","note_text"
      Remaining lines : blank / space padding (ignored)

    CPCe uses twips as its internal coordinate unit (1 twip = 1/1440 inch).
    At standard 96 DPI (Windows default): 1 pixel = 15 twips.
    The header's int_width / int_height encodes the exact scale:
        pixel_x = twip_x * img_width_px / int_width
        pixel_y = twip_y * img_height_px / int_height

    Image path resolution order:
      1. Original absolute path from the .cpc header
      2. Basename of that path searched in image_dir (if provided)
      3. Basename searched in the same directory as the .cpc file
      4. Fallback: pixel dimensions estimated from twips ÷ 15 (96 DPI)

    Returns (ImageAnnotation, ImportResult). ImageAnnotation is None on failure.
    """
    warnings: list[str] = []

    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            raw_lines = f.read().splitlines()
    except Exception as exc:
        return None, ImportResult(False, f"Cannot read .cpc file: {exc}")

    # Strip trailing whitespace; remove truly blank lines only at the end
    lines = [ln.rstrip() for ln in raw_lines]

    if len(lines) < 7:
        return None, ImportResult(False, "File too short to be a valid .cpc file.")

    # ── Parse header (line 0) ──────────────────────────────────────────
    try:
        reader = csv.reader(io.StringIO(lines[0]))
        header = [f.strip() for f in next(reader)]
    except Exception as exc:
        return None, ImportResult(False, f"Cannot parse header line: {exc}")

    if len(header) < 4:
        return None, ImportResult(False, f"Header has too few fields ({len(header)}): {lines[0]}")

    orig_image_path = header[1].strip()
    try:
        int_width  = float(header[2])   # CPCe internal width  (image_width_px × 15)
        int_height = float(header[3])   # CPCe internal height (image_height_px × 15)
    except (ValueError, IndexError) as exc:
        return None, ImportResult(False, f"Cannot parse image dimensions from header: {exc}")

    if int_width <= 0 or int_height <= 0:
        return None, ImportResult(False, f"Invalid internal dimensions: {int_width}×{int_height}")

    # ── Resolve image file and actual pixel dimensions ─────────────────
    # Normalize Windows backslashes before extracting basename so this works on Linux/macOS
    image_basename = os.path.basename(orig_image_path.replace("\\", "/"))
    resolved_path = orig_image_path      # may be overwritten below
    img_width: Optional[int] = None
    img_height: Optional[int] = None

    search_dirs: list[str] = []
    if image_dir:
        search_dirs.append(image_dir)
    search_dirs.append(os.path.dirname(os.path.abspath(path)))

    # Try original path first, then basename in search dirs
    candidates = [orig_image_path] + [os.path.join(d, image_basename) for d in search_dirs]
    for candidate in candidates:
        if os.path.exists(candidate):
            try:
                from PIL import Image as PILImage
                with PILImage.open(candidate) as img:
                    img_width, img_height = img.size
                resolved_path = candidate
                break
            except Exception:
                pass

    if img_width is None:
        # Fallback: derive from twips assuming 96 DPI (15 twips/px)
        img_width  = round(int_width  / 15)
        img_height = round(int_height / 15)
        warnings.append(
            f"Image not found: '{image_basename}'. "
            f"Estimated dimensions {img_width}×{img_height} px from .cpc header (96 DPI)."
        )

    scale_x = img_width  / int_width
    scale_y = img_height / int_height

    def _twips_to_px(tx: float, ty: float) -> tuple[float, float]:
        return round(tx * scale_x, 2), round(ty * scale_y, 2)

    # ── Parse border rectangle (lines 1–4) ────────────────────────────
    border_corners: list[tuple[float, float]] = []
    for i in range(1, 5):
        if i >= len(lines):
            break
        try:
            parts = lines[i].split(",")
            tx, ty = float(parts[0]), float(parts[1])
            border_corners.append(_twips_to_px(tx, ty))
        except Exception as exc:
            warnings.append(f"Cannot parse border corner on line {i+1}: {exc}")

    # ── Parse point count (line 5) ─────────────────────────────────────
    try:
        n_points = int(lines[5].strip())
    except (ValueError, IndexError):
        return None, ImportResult(False, f"Cannot parse point count on line 6: '{lines[5]}'")

    coord_end   = 6 + n_points          # exclusive
    label_end   = coord_end + n_points  # exclusive

    if coord_end > len(lines):
        return None, ImportResult(False,
            f".cpc declares {n_points} points but file has only {len(lines) - 6} lines after header.")

    # ── Parse point coordinates (lines 6..coord_end-1) ────────────────
    points: list[Point] = []
    for i in range(6, coord_end):
        try:
            parts = lines[i].split(",")
            tx, ty = float(parts[0]), float(parts[1])
            px_x, px_y = _twips_to_px(tx, ty)
            points.append(Point(x=px_x, y=px_y, index=i - 5))  # 1-based index
        except Exception as exc:
            warnings.append(f"Cannot parse point coordinate on line {i+1}: '{lines[i]}' ({exc})")

    # ── Parse labeled points (lines coord_end..label_end-1) ───────────
    label_map: dict[int, tuple[str, str]] = {}   # index → (code, note)
    for i in range(coord_end, min(label_end, len(lines))):
        line = lines[i].strip()
        if not line or set(line) == {' ', '"'}:
            continue
        try:
            reader = csv.reader(io.StringIO(line), skipinitialspace=True)
            fields = [f.strip().strip('"') for f in next(reader)]
            if len(fields) >= 2:
                pt_idx = int(fields[0])
                code   = fields[1].strip()
                note   = fields[3].strip() if len(fields) > 3 else ""
                if code:
                    label_map[pt_idx] = (code, note)
        except Exception:
            pass

    for pt in points:
        if pt.index in label_map:
            pt.label = label_map[pt.index][0]

    # ── Build ImageAnnotation ──────────────────────────────────────────
    ann = ImageAnnotation(
        image_path=resolved_path,
        points=points,
        image_width=img_width,
        image_height=img_height,
    )

    labeled = sum(1 for p in points if p.label)
    msg = (
        f"Imported {len(points)} points ({labeled} labeled) "
        f"from '{image_basename}'."
    )
    return ann, ImportResult(True, msg, warnings)
