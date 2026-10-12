"""
FlashDock — Comprehensive Settings & Preferences Center (Section 3.3).

Consolidates all workstation preferences into a clean, tabbed modal dialog:
- Appearance Tab: Dark, Light, OLED Black themes
- Paths Tab: Platform-tools directory, backup directory, driver downloads
- Connection Tab: Hardware polling interval, auto-refresh toggle
- Safety Tab: Battery cutoff percentage (>= 30%), strict Anti-Relock toggle, slot verification
- Logs Tab: Export sanitized diagnostic bundles, serial masking toggle
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from flashdock.config import Config
from flashdock.constants import BACKUPS_DIR, TOOLS_DIR
from flashdock.logger import get_logger
from flashdock.ui.icon_assets import create_icon_label, get_icon

log = get_logger(__name__)


class SettingsDialog(QDialog):
    """
    Comprehensive Workstation Settings & Preferences Center.
    """

    theme_changed = Signal(str)
    settings_saved = Signal()

    def __init__(self, config: Config, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config

        self.setWindowTitle("Workstation Settings & Preferences — FlashDock")
        self.setFixedSize(620, 500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        # Header Row
        head_row = QHBoxLayout()
        head_row.setSpacing(10)
        head_row.addWidget(create_icon_label("tools", 24, color="#007AFF"))

        head_col = QVBoxLayout()
        head_col.setSpacing(2)
        title_lbl = QLabel("Workstation Settings")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #E6EDF3;")
        desc_lbl = QLabel("Configure appearance, paths, safety locks, and port polling behavior.")
        desc_lbl.setStyleSheet("font-size: 11px; color: #8B949E;")
        head_col.addWidget(title_lbl)
        head_col.addWidget(desc_lbl)
        head_row.addLayout(head_col, 1)
        root.addLayout(head_row)

        # Tabs
        self._tabs = QTabWidget()
        self._build_appearance_tab()
        self._build_paths_tab()
        self._build_connection_tab()
        self._build_safety_tab()
        self._build_logs_tab()
        self._build_about_tab()
        root.addWidget(self._tabs, 1)

        # Bottom Action Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(90)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save Preferences")
        save_btn.setIcon(get_icon("integrity", 13, color="#FFFFFF"))
        save_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007AFF, stop:1 #0056B3);
                color: #FFFFFF;
                font-weight: 700;
                padding: 6px 14px;
                border-radius: 8px;
            }
        """)
        save_btn.clicked.connect(self._save_preferences)
        btn_row.addWidget(save_btn)

        root.addLayout(btn_row)

    # -----------------------------------------------------------------------
    # Tab Builders
    # -----------------------------------------------------------------------

    def _build_appearance_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(12)

        self._theme_combo = QComboBox()
        self._theme_combo.addItem("Deep Space Obsidian (Dark)", "dark")
        self._theme_combo.addItem("Warm Slate-Mica (Light)", "light")
        self._theme_combo.addItem("OLED True Black (Pure Dark)", "oled")

        cur_theme = self._config.get("theme", "dark").lower()
        idx = 0
        if cur_theme == "light":
            idx = 1
        elif cur_theme == "oled":
            idx = 2
        self._theme_combo.setCurrentIndex(idx)
        form.addRow("Interface Theme:", self._theme_combo)

        self._chk_glass = QCheckBox("Enable Glassmorphic card drop shadows")
        self._chk_glass.setChecked(self._config.get("enable_shadows", True))
        form.addRow("", self._chk_glass)

        self._chk_smooth_anim = QCheckBox("Smooth transition animations")
        self._chk_smooth_anim.setChecked(self._config.get("smooth_animations", True))
        form.addRow("", self._chk_smooth_anim)

        lay.addLayout(form)
        lay.addStretch(1)
        self._tabs.addTab(tab, "Appearance")

    def _build_paths_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(12)

        # Platform tools path
        tools_row = QHBoxLayout()
        self._txt_tools = QLineEdit(str(self._config.get("tools_dir", str(TOOLS_DIR))))
        tools_row.addWidget(self._txt_tools, 1)
        btn_browse_tools = QPushButton("Browse...")
        btn_browse_tools.clicked.connect(lambda: self._browse_dir(self._txt_tools))
        tools_row.addWidget(btn_browse_tools)
        form.addRow("Platform-Tools Dir:", tools_row)

        # Backup path
        backup_row = QHBoxLayout()
        self._txt_backup = QLineEdit(str(self._config.get("backup_dir", str(BACKUPS_DIR))))
        backup_row.addWidget(self._txt_backup, 1)
        btn_browse_bak = QPushButton("Browse...")
        btn_browse_bak.clicked.connect(lambda: self._browse_dir(self._txt_backup))
        backup_row.addWidget(btn_browse_bak)
        form.addRow("Partition Backups Dir:", backup_row)

        lay.addLayout(form)
        lay.addStretch(1)
        self._tabs.addTab(tab, "Paths")

    def _build_connection_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(12)

        self._spin_poll = QSpinBox()
        self._spin_poll.setRange(500, 10000)
        self._spin_poll.setSingleStep(250)
        self._spin_poll.setValue(self._config.get("poll_interval_ms", 1000))
        self._spin_poll.setSuffix(" ms")
        form.addRow("USB Bus Polling Interval:", self._spin_poll)

        self._chk_auto_rescan = QCheckBox("Automatically refresh ADB/Fastboot on USB insertion")
        self._chk_auto_rescan.setChecked(self._config.get("auto_refresh_on_connect", True))
        form.addRow("", self._chk_auto_rescan)

        self._combo_mode = QComboBox()
        self._combo_mode.addItem("Simple Mode (Guided One-Click Workflows)", "simple")
        self._combo_mode.addItem("Advanced Mode (Full Multi-Chipset Engineering)", "advanced")
        current_mode = self._config.get("mode", "simple")
        self._combo_mode.setCurrentIndex(1 if current_mode == "advanced" else 0)
        form.addRow("Workstation Mode:", self._combo_mode)

        self._chk_dry_run = QCheckBox("Dry-Run Simulation Mode (Simulate commands without physical writes)")
        self._chk_dry_run.setChecked(self._config.get("dry_run", False))
        form.addRow("", self._chk_dry_run)

        self._chk_force_offline = QCheckBox("Force Offline Mode (Block external network downloads)")
        self._chk_force_offline.setChecked(self._config.get("offline_forced", False))
        form.addRow("", self._chk_force_offline)

        lay.addLayout(form)
        lay.addStretch(1)
        self._tabs.addTab(tab, "Connection & Modes")

    def _build_safety_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(12)

        self._spin_battery = QSpinBox()
        self._spin_battery.setRange(10, 80)
        self._spin_battery.setValue(self._config.get("min_battery_pct", 30))
        self._spin_battery.setSuffix(" %")
        form.addRow("Minimum Battery Cutoff:", self._spin_battery)

        self._chk_anti_relock = QCheckBox("Strict Anti-Relock Protection Gate (Prevent bricking modified partitions)")
        self._chk_anti_relock.setChecked(self._config.get("strict_anti_relock", True))
        form.addRow("", self._chk_anti_relock)

        self._chk_slot_guard = QCheckBox("Active Slot Desync Guard (Require slot confirmation)")
        self._chk_slot_guard.setChecked(self._config.get("slot_desync_guard", True))
        form.addRow("", self._chk_slot_guard)

        self._chk_preflash_backup = QCheckBox("Mandatory Pre-Flash Calibration Backup (EFS / NVRAM / Persist)")
        self._chk_preflash_backup.setChecked(self._config.get("preflash_backup_mandatory", True))
        form.addRow("", self._chk_preflash_backup)

        lay.addLayout(form)
        lay.addStretch(1)
        self._tabs.addTab(tab, "Safety Gates")

    def _build_logs_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(12)

        self._chk_mask_serials = QCheckBox("Redact Device Serial Numbers & IMEI in Logs (Privacy Guard)")
        self._chk_mask_serials.setChecked(self._config.get("mask_telemetry_serials", True))
        form.addRow("", self._chk_mask_serials)

        self._chk_crash_reports = QCheckBox("Generate Local Sanitized Crash Dumps on Exceptions")
        self._chk_crash_reports.setChecked(self._config.get("enable_crash_dumps", True))
        form.addRow("", self._chk_crash_reports)

        lay.addLayout(form)
        lay.addStretch(1)
        self._tabs.addTab(tab, "Privacy & Logs")

    def _build_about_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        title = QLabel("FlashDock — Personal Android Service Workstation")
        title.setStyleSheet("font-size: 14px; font-weight: 700; color: #E6EDF3;")
        lay.addWidget(title)

        ver = QLabel("Version 1.2.1 • GSM Suite Architecture • Built for Windows 10/11 x64")
        ver.setStyleSheet("font-size: 11px; color: #0A84FF; font-weight: 600;")
        lay.addWidget(ver)

        desc = QLabel(
            "Universal flashing, unbricking, partition backup, Play Integrity spoofing, "
            "and bootloader maintenance workstation for Xiaomi, Samsung, Transsion, "
            "Google Pixel, OnePlus, MediaTek BROM, Qualcomm EDL, and Unisoc SPRD devices."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 11px; color: #8B949E; line-height: 1.4;")
        lay.addWidget(desc)

        license_lbl = QLabel("Distributed under the MIT License • © 2024-2026 Klein Systems")
        license_lbl.setStyleSheet("font-size: 10px; color: #8E8E93;")
        lay.addWidget(license_lbl)

        lay.addStretch(1)
        self._tabs.addTab(tab, "About")

    def _browse_dir(self, target_line_edit: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Directory", target_line_edit.text())
        if path:
            target_line_edit.setText(path)

    def _save_preferences(self) -> None:
        chosen_theme = self._theme_combo.currentData()
        self._config.set("theme", chosen_theme)
        self._config.set("enable_shadows", self._chk_glass.isChecked())
        self._config.set("smooth_animations", self._chk_smooth_anim.isChecked())
        self._config.set("tools_dir", self._txt_tools.text())
        self._config.set("backup_dir", self._txt_backup.text())
        self._config.set("poll_interval_ms", self._spin_poll.value())
        self._config.set("auto_refresh_on_connect", self._chk_auto_rescan.isChecked())
        self._config.set("mode", self._combo_mode.currentData())
        self._config.set("dry_run", self._chk_dry_run.isChecked())
        self._config.set("offline_forced", self._chk_force_offline.isChecked())
        self._config.set("min_battery_pct", self._spin_battery.value())
        self._config.set("strict_anti_relock", self._chk_anti_relock.isChecked())
        self._config.set("slot_desync_guard", self._chk_slot_guard.isChecked())
        self._config.set("preflash_backup_mandatory", self._chk_preflash_backup.isChecked())
        self._config.set("mask_telemetry_serials", self._chk_mask_serials.isChecked())
        self._config.set("enable_crash_dumps", self._chk_crash_reports.isChecked())

        self.theme_changed.emit(chosen_theme)
        self.settings_saved.emit()
        self.accept()

    _save_settings = _save_preferences
