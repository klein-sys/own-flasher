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
        ('flashdock/resources', 'flashdock/resources'),
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
        'flashdock.brands.transsion',
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
        'flashdock.core.diagnostics_engine',
        'flashdock.ui.screens.diagnostics_screen',
        'flashdock.core.mtk',
        'flashdock.core.unisoc',
        'flashdock.ui.screens.mtk_unisoc_screen',
        'flashdock.core.tools_manager',
        'flashdock.ui.screens.downloads_screen',
        'flashdock.core.bootloop_fixer',
        'flashdock.ui.screens.unbrick_screen',
        'flashdock.core.integrity',
        'flashdock.ui.screens.integrity_screen',
        'flashdock.core.troubleshooter',
        'flashdock.ui.screens.logs_help_screen',
        'flashdock.core.selftest',
        'flashdock.ui.widgets.selftest_dialog',
        'flashdock.core.crash_reporter',
        'flashdock.ui.widgets.crash_dialog',
        'flashdock.tools.scrcpy',
        'flashdock.ui.widgets.scrcpy_dialog',
        'flashdock.ui.widgets.setup_wizard_dialog',
        'flashdock.ui.widgets.key_guide_dialog',
        'flashdock.ui.icon_assets',
        'flashdock.ui.brand_assets',
        'flashdock.workers.device_monitor',
        'flashdock.workers.flash_engine',
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
    icon='flashdock/resources/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FlashDock_Dist',
)
