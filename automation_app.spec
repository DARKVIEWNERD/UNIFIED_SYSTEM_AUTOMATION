# -*- mode: python ; coding: utf-8 -*-
# automation_app.spec

import re
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# ── AUTO-READ requirements.txt ───────────────────────────────
# Just add a new library to requirements.txt — no need to touch this file.
def parse_requirements(filename='requirements.txt'):
    packages = []
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Strip version specifiers e.g. selenium>=4.15.0 → selenium
            pkg = re.split(r'[>=<!;]', line)[0].strip()
            # Normalize: pip uses hyphens, Python imports use underscores
            pkg = pkg.replace('-', '_')
            packages.append(pkg)
    return packages

requirements = parse_requirements()

# Build hidden_imports from requirements + collect all their submodules
hidden_imports = []
datas = []

for pkg in requirements:
    hidden_imports += collect_submodules(pkg)
    try:
        datas += collect_data_files(pkg)
    except Exception:
        pass  # not all packages have data files

# ── YOUR LOCAL PACKAGES ──────────────────────────────────────
# Only update this if you add new local folders/modules
hidden_imports += [
    'tkinter', 'tkinter.ttk', 'tkinter.messagebox',
    'tkinter.filedialog', 'tkinter.scrolledtext',
    'managers', 'managers.config_manager', 'managers.log_manager',
    'tabs', 'tabs.Automation_Tab', 'tabs.config_tab', 'tabs.view_tab',
    'constants', 'constants.ui',
    'utils', 'utils.file_watcher',
]

# ── JSON FILES STAY OUTSIDE THE EXE ─────────────────────────
# config.json and custom_patterns.json are NOT bundled inside.
# They sit next to the .exe so users can edit them freely.
# (See resource_path.py for how the app reads them)

a = Analysis(
    ['main2.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'PIL', 'PyQt5', 'PyQt6', 'wx'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AutomationApp',       # <-- Change to your preferred exe name
    debug=False,
    strip=False,
    upx=True,
    console=False,              # False = no black console window (GUI app)
    # icon='assets/icon.ico',  # <-- Uncomment if you have an icon
)
