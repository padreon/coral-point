# coralX — Rewrite Roadmap: Python/PyQt6 → Tauri + Rust

## Background

coralX is currently built on Python 3.11 + PyQt6 (~4,900 lines of code). This rewrite migrates all features to **Tauri 2.x** (Rust backend) + **React/TypeScript** (frontend), with three primary goals:

1. Reduce bundle size from ~80–100 MB (PyInstaller) to **5–15 MB** (Tauri)
2. Permanently eliminate Windows DLL issues (WinError 1114 / `c10.dll`)
3. Native per-platform installer with no Python dependency for end users

---

## Chosen Stack

| Layer | Choice | Reason |
|---|---|---|
| Backend | Rust + Tauri 2.x | Native, small bundle, memory-safe |
| Frontend | React 18 + TypeScript + Vite 5 | Wide ecosystem, first-class Tauri support |
| Canvas | Konva.js / react-konva | Built-in transform matrix + hit-testing |
| State | Zustand | Minimal, no boilerplate, IPC-friendly |
| Table | TanStack Table v8 | Headless, inline-edit support |
| Tree | react-arborist | True tree widget with virtualization |
| Excel write | `rust_xlsxwriter` | Actively maintained, full multi-sheet support |
| Excel read | `calamine` | CPCe import, fast, no C dependencies |
| Image | `image` crate | Dimension reading + thumbnails; no OpenCV needed |
| AI | Python subprocess | Keeps ultralytics optional; no model conversion needed |

---

## Target Folder Structure

```
coralx/
├── src/                              # React/TS frontend
│   ├── components/
│   │   ├── canvas/                   # ImageCanvas, PointOverlay, BorderLayer
│   │   ├── panels/                   # StationTree, PointsTable, CodesPanel
│   │   └── dialogs/                  # CalibrationDialog, AILabelDialog, ImportDialogs
│   ├── hooks/                        # useProject, useCanvas, useKeyboard
│   ├── stores/                       # Zustand slices
│   ├── ipc/                          # Typed invoke() wrappers
│   └── types/                        # TypeScript mirrors of Rust structs
├── src-tauri/
│   ├── src/
│   │   ├── main.rs
│   │   ├── lib.rs
│   │   ├── models/project.rs         # Point, ImageAnnotation, Station, Project
│   │   ├── commands/                 # project, points, analysis, export, import, image, ai
│   │   └── core/                     # point_generator, analysis, statistics, exporter, importer, ai_labeler
│   ├── Cargo.toml
│   └── tauri.conf.json
├── resources/
│   └── ai_helper.py                  # Bundled AI subprocess helper
├── .gitignore
├── package.json
└── vite.config.ts
```

---

## .gitignore

```gitignore
# Rust
target/

# Node
node_modules/
dist/

# Tauri generated
src-tauri/gen/
src-tauri/WixTools/

# OS
.DS_Store
Thumbs.db
desktop.ini

# IDE
.vscode/
.idea/
*.swp

# Logs
*.log

# AI/ML
*.pt
runs/
datasets/
```

---

## Implementation Phases

---

### Phase 0 — Project Scaffold
**Complexity: Low**

**Goal:** Establish the monorepo layout, toolchain, and all dependency declarations before writing any business logic.

**Tasks:**
- Initialize the project with the official template:
  ```bash
  npm create tauri-app@latest coralx -- --template react-ts
  ```
- Create the folder structure as shown above
- Declare all Cargo dependencies in `src-tauri/Cargo.toml`:
  ```toml
  tauri          = { version = "2", features = ["protocol-asset"] }
  tauri-plugin-dialog  = "2"
  tauri-plugin-fs      = "2"
  tauri-plugin-shell   = "2"
  tauri-plugin-log     = "2"
  serde          = { version = "1", features = ["derive"] }
  serde_json     = "1"
  image          = "0.25"
  rust_xlsxwriter = "0.70"
  calamine       = "0.24"
  csv            = "1"
  tracing        = "0.1"
  tracing-subscriber = { version = "0.3", features = ["env-filter"] }
  tracing-appender   = "0.2"
  rand           = "0.8"
  anyhow         = "1"
  thiserror      = "1"
  ```
- Declare all npm dependencies in `package.json`:
  ```json
  "@tauri-apps/api": "^2",
  "@tauri-apps/plugin-dialog": "^2",
  "@tauri-apps/plugin-fs": "^2",
  "@tauri-apps/plugin-shell": "^2",
  "react": "^18", "react-dom": "^18",
  "konva": "^9", "react-konva": "^18",
  "zustand": "^4",
  "@tanstack/react-table": "^8",
  "react-arborist": "^3",
  "react-resizable-panels": "^2"
  ```
- Create `.gitignore` (see section above)

---

### Phase 1 — Data Models & Project I/O
**Complexity: Low**

**Goal:** Define Rust structs as the single source of truth for all data, with working Tauri commands to open and save projects.

**Tasks:**
- Create `src-tauri/src/models/project.rs` with four serde-derived structs:
  ```rust
  // Field names must match Python exactly so existing .cpce files load without migration
  Point { x, y, index, label: Option<String>, category: Option<String> }
  ImageAnnotation { image_path, points, image_width, image_height, scale_factor, scale_unit }
  Station { name, depth_m, date, gps_lat, gps_lon, notes, annotations }
  Project { name, point_count, point_distribution, border_exclusion, border_rect, coral_codes, coral_groups, stations }
  ```
- Implement methods: `Project::flat_annotations()`, `labeled_count()`, `is_complete()`, `coverage_stats()`
- Implement Tauri commands: `load_project`, `save_project`, `new_project`
- **Legacy format migration:** in `load_project`, detect JSON with a top-level `"annotations"` key but no `"stations"` key → wrap those annotations in a single `Station { name: "Station 1", ... }` (mirrors Python's `Project.load()`)

**Reference:** `src/models/project.py` — JSON field names must match exactly

---

### Phase 2 — Core Algorithms
**Complexity: Medium**

**Goal:** Port the three Python core modules to Rust with no external dependencies beyond `rand` and standard `f64` math.

**Tasks:**

#### Point Generator (`src-tauri/src/core/point_generator.rs`)
- Port `generate_points(width, height, count, distribution, border, border_rect)`
- **random:** `rng.gen_range(x_min..=x_max)` per point
- **stratified:** divide canvas into N cells, one random point per cell
- **uniform:** manual `linspace`, take first `count` points
- Border exclusion: use `border_rect` bounds if provided, otherwise apply uniform `border` to all four sides

#### Analysis Engine (`src-tauri/src/core/analysis.rs`)
Port all 8 functions from `src/core/analysis.py`:

| Function | Formula |
|---|---|
| `species_richness` | `HashSet::len()` |
| `shannon_index` | `-Σ(p · ln p)` |
| `simpson_index` | `1 - Σn(n-1) / N(N-1)` |
| `pielou_evenness` | `H' / ln(S)` |
| `margalef_richness` | `(S-1) / ln(N)` |
| `fisher_alpha` | Bisection: `α·ln(1 + N/α) - S = 0`, 100 iterations |
| `wilson_ci` | Wilson score interval, z = 1.959964 (95% CI) |
| `coverage_with_ci` | Coverage % + CI per code |

#### Statistics Aggregation (`src-tauri/src/core/statistics.rs`)
- Port `project_summary()`, `station_summary()`, `per_image_table()`, `per_station_table()`
- Return `Vec<HashMap<String, serde_json::Value>>` rows consumed by the exporter

**Key notes:**
- Fisher alpha: plain bisection loop, no external optimizer crate needed
- Wilson CI: hardcode `z = 1.959964` for 95%; add lookup for 90% and 99%
- Excel "Statistics" sheet: column-wise mean/std/stderr with Bessel's correction (`ddof=1`), no `ndarray` crate needed

**Reference:** `src/core/analysis.py`, `src/core/statistics.py`

---

### Phase 3 — Import / Export
**Complexity: High**

**Goal:** Implement all importers and exporters in Rust, producing output identical to the Python versions.

**Tasks:**

#### Exporters
- **CSV** via `csv` crate: call `per_image_table()`, write headers from the union of all keys, fill missing columns with `"0"`
- **Excel** via `rust_xlsxwriter` — 7 sheets in order:
  1. Summary, 2. Group Coverage, 3. Per Station, 4. Per Image, 5. Statistics, 6. Cover Area *(only when calibration data exists)*, 7. Raw Points
- **Coral Codes** — `.json` (round-trip with groups array) or `.csv`/`.tsv` (flat: code, description, group, color)

#### Importers (all return `ImportResult { success, message, warnings }`)
- **CPCe `.cpc`** (most complex): pipe-delimited parsing, twips→pixels conversion (`pixel = twip * img_width / int_width`), 4-corner border parsing, N coordinate lines, N label lines
- **CPCe Excel** via `calamine`: detect "Raw Points"/"Data" sheet, detect columns via alias lists
- **Coral Codes `.txt`**: category→sub-code hierarchy with `NOTES` separator
- **Station Metadata CSV**: column alias detection (`station`/`site`/`transect`, `depth`/`depth_m`, etc.)
- **Labeled Points CSV/Excel**: match rows to existing annotations by image basename

**Reference:** `src/core/exporter.py`, `src/core/importer.py`

---

### Phase 4 — Image Bridge
**Complexity: Low**

**Goal:** Serve images from disk to the React frontend without copying bytes across IPC.

**Tasks:**
- `get_image_dimensions(path) → (u32, u32)` via `image` crate (replaces `cv2.imread`)
- Enable **Tauri asset protocol** in `tauri.conf.json`:
  ```json
  "security": { "assetProtocol": { "enable": true, "scope": ["$HOME/**", "$DOCUMENT/**"] } }
  ```
  Frontend renders: `<img src={convertFileSrc(annotation.image_path)} />`
- `get_thumbnail(path) → Vec<u8>`: resize to 48×48 via `image::imageops::thumbnail()`, encode as PNG
- `compute_scale_factor(pixel_dist, real_dist) → f64`: `pixel_dist / real_dist`

---

### Phase 5 — Frontend Scaffold & State
**Complexity: Medium**

**Goal:** Set up TypeScript types, Zustand state, and the 3-panel layout skeleton before any real UI components.

**Tasks:**
- Create `src/types/project.ts` — mirror every Rust struct field (`Option<T>` → `T | null`)
- Create `src/ipc/` — one file per command group, typed `invoke<T>()`:
  ```typescript
  export const loadProject = (path: string) => invoke<Project>('load_project', { path });
  ```
- Create two Zustand slices:
  - `projectStore`: authoritative project document + `isDirty` flag
  - `uiStore`: selection, zoom, pan, borderMode — transient, not persisted
- Layout skeleton: CSS Grid 3-panel (left 280px, center flex, right 320px) with `react-resizable-panels`

---

### Phase 6 — Image Canvas
**Complexity: High**

**Goal:** Port `ImageCanvas` from PyQt6 to react-konva with all zoom/pan/point/border behaviors.

**Tasks:**
- **4 Konva layers:** `backgroundLayer` (image), `borderLayer`, `pointsLayer`, `interactionLayer`
- **Zoom/Pan:** wheel → `zoom *= 1.25 or 0.8`; middle-mouse drag → pan delta; clamp zoom 0.1–10
- **Point overlay:**
  - Red = unlabeled, Green = labeled, Yellow = selected
  - Screen radius = `POINT_RADIUS / zoom` (constant screen size regardless of zoom level)
- **Hit test:** Manhattan distance `POINT_RADIUS / zoom + 4` in image-space — must match Python's `_hit_point()` exactly
- **Click-to-label:** click point → HTML context menu at pointer position → select code → update Zustand + `invoke('update_point_label')`
- **Border drawing:** 2-point / 4-point state machine; dashed rect preview; ESC cancels
- **Keyboard:**
  - Arrow keys: cycle through points, auto-pan to keep selected point centered
  - Enter: open label menu for the selected point
  - Shortcut buffer: accumulate keystrokes; after 700ms timeout, match against `coral_codes`; on match, label and advance

**Reference:** `src/ui/image_canvas.py` — coordinate system, hit-test formula, keyboard buffer, border state machine

---

### Phase 7 — Panels & Dialogs
**Complexity: Medium**

**Goal:** Build all non-canvas UI: station tree, points table, codes panel, and all dialogs.

**Tasks:**

**Station Tree (react-arborist):**
- Nodes: station (collapsible) → image (with lazy-loaded thumbnail)
- Filter checkbox: show only incomplete images
- Right-click: Edit Metadata, Add Images, Remove Station

**Points Table (TanStack Table v8):**
- Columns: `#`, X, Y, Label (inline `<select>` with autocomplete from `coral_codes`)
- Bidirectional sync with canvas selection

**Codes Panel:**
- Quick-label buttons grouped by `coral_groups`
- Clicking a button labels the selected point immediately, no menu needed

**Dialogs:**

| Dialog | Description |
|---|---|
| CalibrationDialog | 2 canvas clicks → enter real-world distance → compute `scale_factor`; apply-to-all option |
| AILabelDialog | Model picker, confidence (0–1), crop size (32–512px), scope, class mapping table, real-time progress |
| ImportResultDialog | Success/error message + scrollable warnings list |
| CoralCodesMergeDialog | Radio: Merge / Replace |
| StationMergeDialog | Per conflicting station: Skip / Merge / Replace |
| CpceImportDialog | New project vs. merge into current; image directory picker |
| StationMetadataDialog | Form: name, depth, date, GPS, notes |
| ManageGroupsDialog | Editable table of group names + codes (comma-separated) |
| **RelinkImagesDialog** | **(New feature)** Remap broken absolute image paths — addresses the known limitation from the Python version |

---

### Phase 8 — AI Auto-Label
**Complexity: Medium**

**Goal:** Preserve the optional YOLOv8 workflow via Python subprocess, keeping ultralytics out of the bundle.

**Strategy: Python subprocess via `tauri-plugin-shell`**

- Bundle `resources/ai_helper.py` — accepts JSON config on stdin, emits JSON progress lines on stdout
- Rust spawns the subprocess and forwards output as Tauri events:
  ```rust
  #[tauri::command]
  pub async fn ai_label_start(app: AppHandle, ...) -> Result<(), String> {
      // spawn: python3 resources/ai_helper.py
      // read stdout lines → emit event "ai_progress"
      // on completion → emit event "ai_done"
  }
  ```
- `ai_check_model`: validate that `python3` + `ultralytics` are available on PATH
- `ai_suggest_mapping`: pure Rust fuzzy match — class names vs. `coral_codes` keys/descriptions (port of `AILabeler.suggest_mapping`)
- Frontend: `listen('ai_progress', ...)` drives the real-time progress dialog
- `ai_label_cancel`: kill the subprocess

**Why not ONNX in-process?** Requires users to convert their `.pt` models to `.onnx`, breaking compatibility with existing model files.

---

### Phase 9 — Logging & Error Handling
**Complexity: Low**

**Goal:** Structured logging with platform-specific file paths and a panic hook that surfaces errors to the user.

**Tasks:**
- `tracing` + `tracing-appender`: rolling file log (1 MB, 3 backups)
- Log paths matching the Python version:
  - Windows: `%APPDATA%/coralX/coralX.log`
  - macOS: `~/Library/Logs/coralX/coralX.log`
  - Linux: `$XDG_DATA_HOME/coralX/coralX.log`
- Panic hook: `std::panic::set_hook(...)` → `tracing::error!` + emit `"app_panic"` Tauri event → frontend shows modal with log file path
- `get_log_path() → String` command for the "Open Log File" menu item

---

### Phase 10 — Build & Distribution
**Complexity: Low**

**Goal:** Multi-platform CI/CD using the Tauri bundler as a drop-in replacement for PyInstaller.

**Tasks:**
- Create `.github/workflows/release.yml` using `tauri-apps/tauri-action@v0`:
  ```yaml
  strategy:
    matrix:
      include:
        - platform: 'ubuntu-22.04'
        - platform: 'macos-latest'
          args: '--target aarch64-apple-darwin'
        - platform: 'windows-latest'
  ```
- Expected bundle sizes per platform:

  | Platform | Format | Estimated size |
  |---|---|---|
  | Windows | `.msi` + `.exe` | 5–12 MB |
  | macOS | `.dmg` + `.app` | 8–15 MB |
  | Linux | `.AppImage` + `.deb` | 6–12 MB |

- **Code signing:**
  - Windows: Authenticode via `TAURI_PRIVATE_KEY` + `TAURI_KEY_PASSWORD` in GitHub Secrets
  - macOS: Apple Developer ID + notarization via `APPLE_CERTIFICATE`, `APPLE_ID`, `APPLE_TEAM_ID`, etc.
  - Linux: not required for AppImage
- Bundle `resources/ai_helper.py` via `tauri.conf.json`:
  ```json
  "bundle": { "resources": ["resources/ai_helper.py"] }
  ```

---

## Phase Dependency Order

```
Phase 0 (scaffold)
  └─ Phase 1 (models + I/O)
       ├─ Phase 2 (algorithms)
       ├─ Phase 3 (import/export)
       └─ Phase 4 (image bridge)
            └─ Phase 5 (frontend scaffold)
                 ├─ Phase 6 (canvas)
                 └─ Phase 7 (panels + dialogs)
                      └─ Phase 8 (AI dialog)
Phase 9 (logging)  ← can be done any time after Phase 1
Phase 10 (build)   ← last
```

**Verification checkpoints:**
1. After Phase 1: `load_project` round-trips an existing `.cpce` fixture without data loss
2. After Phase 4: a local JPEG renders in the React frontend via asset protocol
3. After Phase 6: full annotation workflow works end-to-end (open → generate → label)
4. After Phase 7: CSV and Excel export produce files identical to the Python version for the same input
5. After Phase 8: AI auto-label runs with a sample `.pt` model and applies labels correctly
6. After Phase 10: CI builds produce installers on all three platforms; Windows installer runs with no DLL errors

---

## Gotchas & Key Decisions

| # | Issue | Solution |
|---|---|---|
| 1 | Point coordinates are **image-space pixels**, not normalized | Store `x, y` as raw `f64` pixels; do not normalize to 0–1 |
| 2 | Hit-test uses **Manhattan distance**, not Euclidean | Port `POINT_RADIUS / zoom + 4` from Python's `_hit_point()` exactly |
| 3 | `.cpce` files store **absolute** image paths | Keep the same behavior; add RelinkImagesDialog as a new feature |
| 4 | Fisher alpha requires **iterative root-finding** | 100-iteration bisection; validate: S=8, N=200 → alpha ≈ 2.41 |
| 5 | Excel "Statistics" sheet needs **mean/std/stderr** without NumPy | Column-wise `Vec<f64>`, Bessel's correction (`n-1`), no `ndarray` crate |
| 6 | Wilson CI requires z-score from `scipy.stats.norm.ppf` | Hardcode: 95% = 1.959964, 90% = 1.644854, 99% = 2.575829 |
| 7 | CPCe twips: `int_width = img_width_px × 15` at 96 DPI | Use actual dimensions from `image` crate when the file is found |
| 8 | Labeling one point must not re-render the full canvas | Immutable nested `updateAnnotation()`; separate Konva layers |
