# -*- mode: python ; coding: utf-8 -*-
"""
FlashDock — PyInstaller spec file.

Builds a single-folder distribution (not one-file) for better startup
performance and easier debugging.  The output goes into dist/FlashDock/.

Usage:
    pyinstaller flashdock.spec

The resulting dist/FlashDock/ folder can be zipped and distributed.
"""

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Include resources and bundled platform tools
        ('resources', 'resources'),
        ('data/tools', 'data/tools'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtNetwork',
        'flashdock.brands',
        'flashdock.brands.google',
        'flashdock.brands.xiaomi',
        'flashdock.brands.samsung',
        'flashdock.brands.others',
        'flashdock.core.safety',
        'flashdock.core.backup',
        'flashdock.ui.widgets.flash_shield',
        'flashdock.ui.screens.backup_screen',
        'flashdock.core.rooting',
        'flashdock.ui.screens.root_screen',
        'flashdock.core.modules',
        'flashdock.ui.screens.modules_screen',
        'flashdock.core.return_stock',
        'flashdock.ui.screens.return_stock_screen',
        'flashdock.ui.widgets.side_terminal',
        'flashdock.ui.widgets.workflow_guide',
        'flashdock.ui.widgets.root_library_dialog',
        'flashdock.core.repository',
        'flashdock.core.rom_flasher',
        'flashdock.ui.screens.flash_rom_screen',
        'flashdock.core.diagnostics',
        'flashdock.ui.screens.diagnostics_screen',
        'flashdock.core.mtk',
        'flashdock.core.unisoc',
        'flashdock.ui.screens.mtk_unisoc_screen',
        'flashdock.core.tools_manager',
        'flashdock.ui.screens.downloads_screen',
        'flashdock.core.bootloop_fixer',
        'flashdock.ui.screens.unbrick_screen',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'tkinter',
        'test',
        'unittest',
        'pytest',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FlashDock',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window — it's a GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # TODO: Add icon in a later phase
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FlashDock',
)
