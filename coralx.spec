# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for coralX.

Build:
    pip install pyinstaller
    pyinstaller coralx.spec

Output:
    dist/coralX          (Linux / macOS binary or .app)
    dist/coralX.exe      (Windows)
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH)

block_cipher = None

a = Analysis(
    [str(ROOT / "src" / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "data" / "coral_codes_default.json"), "data"),
        (str(ROOT / "data" / "data-training.pt"),         "data"),
    ],
    hiddenimports=[
        # PyQt6 internals that PyInstaller sometimes misses
        "PyQt6.QtPrintSupport",
        "PyQt6.sip",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Dev tools — not needed at runtime
        "ruff", "mypy", "pylint",
        # Large optional packages not needed unless user installs them
        "ultralytics", "torch", "torchvision",
        # Notebook / IPython stack
        "IPython", "ipykernel", "jupyter",
        "matplotlib", "tkinter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="coralX",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,          # compress with UPX if available (smaller binary)
    console=False,     # no terminal window on Windows / macOS
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,         # add icon path here when available, e.g. "assets/icon.ico"
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="coralX",
)

# macOS: wrap in a .app bundle
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="coralX.app",
        icon=None,         # add "assets/icon.icns" when available
        bundle_identifier="com.coralx.app",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "1.0.0",
        },
    )
