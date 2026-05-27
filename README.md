# coralX

**coralX** is an open-source desktop app for coral reef benthic monitoring using the point count method — a modern, cross-platform replacement for [CPCe (Coral Point Count with Excel extensions)](https://hcas.nova.edu/tools-and-resources/cpce/).

Built with Python, PyQt6, and OpenCV.

---

## Why coralX?

CPCe is the de facto standard tool for benthic point count analysis, but it was built in Visual Basic (2006), runs only on Windows, and requires Microsoft Excel. coralX modernizes the workflow:

| | CPCe | coralX |
|---|---|---|
| Platform | Windows only | Windows, macOS, Linux |
| Point distribution | Random only | Random, Stratified, Uniform |
| Export | Excel (requires Office) | CSV + Excel (no Office needed) |
| Diversity indices | Manual calculation | Auto-calculated (Shannon H', Simpson 1-D) |
| Image zoom | Basic | Smooth scroll-to-zoom + pan |
| Project format | Proprietary | Open JSON (`.cpce`) |

---

## Features

- Load underwater transect photos and overlay randomly (or uniformly/stratifiedly) distributed sample points
- Click a point → assign a benthic code from a customizable code list
- Keyboard navigation through points (arrow keys + Enter to label)
- Border exclusion — define a region to confine point generation
- Per-image and project-level coverage statistics
- Shannon-Weaver (H') and Simpson (1-D) diversity indices
- Export to CSV or multi-sheet Excel (Summary / Per Image / Raw Points)
- Import existing CPCe projects and labeled data
- Save/load projects as portable `.cpce` JSON files

---

## Getting Started

### Requirements

- Python 3.10+
- Linux, macOS, or Windows

### Install

```bash
git clone https://github.com/padreon/coralx
cd coralx
pip install -r requirements.txt
```

### Run

```bash
python -m src.main
```

### GitHub Codespaces

1. Open this repo in Codespaces
2. Wait for `postCreateCommand` to finish
3. Open port **6080** in your browser (password: `coral`) — this is the noVNC desktop
4. In the terminal, run `python -m src.main`

---

## Usage

1. **New Project** → `File > New Project`
2. **Add Images** → `File > Add Images` (JPG, PNG, TIFF supported)
3. **Configure points** → set count, distribution method, and border exclusion in the left panel
4. **Generate Points** → click `Generate Points` in the toolbar
5. **Label Points** → click any point on the image → select a coral code from the menu
   - Arrow keys cycle through points; **Enter** opens the label menu for the selected point
6. **Export** → `File > Export CSV` or `File > Export Excel`

---

## Project Structure

```
coralX/
├── src/
│   ├── main.py                    # Entry point
│   ├── ui/
│   │   ├── main_window.py         # App shell, menus, panels, file I/O
│   │   ├── image_canvas.py        # Image viewer with point overlay
│   │   ├── import_dialogs.py      # CPCe import UI
│   │   └── calibration_dialog.py  # Image calibration
│   ├── core/
│   │   ├── point_generator.py     # Random / stratified / uniform points
│   │   ├── statistics.py          # Coverage %, Shannon H', Simpson 1-D
│   │   ├── exporter.py            # CSV and Excel export
│   │   ├── importer.py            # CPCe / CSV import
│   │   └── analysis.py            # Data analysis helpers
│   └── models/
│       └── project.py             # Data models (Project, Station, ImageAnnotation, Point)
├── data/
│   └── coral_codes_default.json   # 12 standard benthic codes
├── .devcontainer/
│   └── devcontainer.json          # GitHub Codespaces config
└── requirements.txt
```

---

## Tech Stack

| Library | Purpose |
|---|---|
| PyQt6 | Desktop UI |
| OpenCV | Image loading and processing |
| NumPy | Point generation and statistics |
| Pandas | Data aggregation and export |
| openpyxl | Excel file generation |

---

## Contributing

Contributions are welcome. To get started:

1. Fork the repo and create a feature branch
2. Make your changes — type hints required on all functions
3. Open a pull request with a clear description of what changed and why

For larger changes, open an issue first to discuss the approach.

---

## Roadmap

- [ ] Dark mode
- [ ] Thumbnail list in image panel
- [ ] Keyboard shortcut labeling (e.g. `H` = HC)
- [ ] Undo/Redo via `QUndoStack`
- [ ] Batch point generation with progress dialog
- [ ] Coverage pie chart (matplotlib embedded)
- [ ] Image calibration (click two points → real-world distance)
- [ ] Area measurement (trace outline → compute area)
- [ ] Image filter/sort (show only incomplete)
- [ ] AI auto-label via YOLOv8 per-point prediction

---

## License

MIT
