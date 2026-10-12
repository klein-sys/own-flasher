"""
FlashDock — Advanced Diagnostics, Debloater & System Tweaks Screen (Phase 10).

Provides:
1. Package Manager Debloater: filter, search, disable, uninstall (user 0), restore,
   and safety guardrails preventing core bricking.
2. Battery & Hardware Health: battery metrics, thermal zones, display and CPU specs.
3. System Tweaks: animation scales (0x, 0.5x, 1x), DPI density modification/reset,
   wireless ADB over TCP/IP 5555, and stay-awake toggle.

Design Constraints:
Strict anti-slop SaaS layout (Zinc monochromatic scale, single #2563eb blue accent,
monospaced tabular numbers for data/metrics, seamless dark/light theme adaptability).
"""

from __future__ import annotations

import re
from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.core.diagnostics import (
    CRITICAL_PROTECTED_PACKAGES,
    BatteryHealthInfo,
    DebloaterManager,
    HardwareHealthInspector,
    HardwareSpecs,
    InstalledPackage,
    SystemTweaker,
)
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.ui.icon_assets import create_icon_label, get_icon

log = get_logger(__name__)


class DiagnosticsScreen(QWidget):
    """Phase 10 screen: Debloater, Hardware & Battery Health, and System Tweaks."""

    def __init__(
        self,
        device_mgr: Optional[DeviceManager] = None,
        adb: Optional[ADB] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._device_mgr = device_mgr
        self._adb = adb or (device_mgr.adb if device_mgr else ADB())
        self._debloater = DebloaterManager(adb=self._adb)
        self._health_inspector = HardwareHealthInspector(adb=self._adb)
        self._tweaker = SystemTweaker(adb=self._adb)

        self._current_device: Optional[DeviceInfo] = None
        self._cached_packages: list[InstalledPackage] = []

        self._build_ui()

    # =========================================================================
    # UI Layout Construction
    # =========================================================================

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 16, 24, 16)
        root_layout.setSpacing(14)

        # ---- Header Bar ----
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        title_h = QHBoxLayout()
        title_h.setSpacing(8)
        title_h.addWidget(create_icon_label("diagnostics", 22))
        title = QLabel("Diagnostics, Debloater & System Tweaks")
        title.setProperty("cssClass", "heading")
        title_h.addWidget(title)
        title_h.addStretch()
        title_col.addLayout(title_h)

        subtitle = QLabel("Remove carrier/OEM bloatware, view hardware & battery telemetry, and tune device scales.")
        subtitle.setProperty("cssClass", "muted")
        title_col.addWidget(subtitle)

        header_row.addLayout(title_col, 1)

        # Connected Device Badge
        self._device_badge = QLabel("No device connected")
        self._device_badge.setProperty("cssClass", "secondary")
        self._device_badge.setStyleSheet("padding: 5px 12px; font-size: 12px;")
        header_row.addWidget(self._device_badge)

        root_layout.addLayout(header_row)

        # ---- Tab Widget ----
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_debloater_tab(), get_icon("box", 16), "Package Debloater")
        self._tabs.addTab(self._build_health_tab(), get_icon("battery", 16), "Hardware & Battery Health")
        self._tabs.addTab(self._build_tweaks_tab(), get_icon("tools", 16), "System Tweaks")
        root_layout.addWidget(self._tabs, 1)

    # -------------------------------------------------------------------------
    # Tab 1: Debloater
    # -------------------------------------------------------------------------

    def _build_debloater_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Filter bar
        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Filter packages or app name (e.g. facebook, vzw, bixby)...")
        self._search_input.textChanged.connect(self._apply_package_filter)
        filter_row.addWidget(self._search_input, 1)

        self._category_combo = QComboBox()
        self._category_combo.addItems([
            "All Categories",
            "Bloatware Only",
            "Carrier Services",
            "Third-Party (User)",
            "OEM System",
            "Protected System",
        ])
        self._category_combo.currentIndexChanged.connect(self._apply_package_filter)
        filter_row.addWidget(self._category_combo)

        self._state_combo = QComboBox()
        self._state_combo.addItems(["All States", "Enabled Only", "Disabled Only"])
        self._state_combo.currentIndexChanged.connect(self._apply_package_filter)
        filter_row.addWidget(self._state_combo)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.setIcon(get_icon("refresh", 14))
        btn_refresh.setToolTip("Reload package list from device")
        btn_refresh.clicked.connect(self.refresh_packages)
        filter_row.addWidget(btn_refresh)

        layout.addLayout(filter_row)

        # Table
        self._pkg_table = QTableWidget()
        self._pkg_table.setColumnCount(4)
        self._pkg_table.setHorizontalHeaderLabels(["Package Name", "Label / Description", "Category", "Status"])
        self._pkg_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self._pkg_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._pkg_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._pkg_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._pkg_table.setColumnWidth(0, 320)
        self._pkg_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._pkg_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self._pkg_table.setAlternatingRowColors(True)
        layout.addWidget(self._pkg_table, 1)

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_select_bloat = QPushButton("Select Recommended Bloat")
        btn_select_bloat.setIcon(get_icon("checklist", 14))
        btn_select_bloat.setToolTip("Auto-select all identified carrier and bloatware packages")
        btn_select_bloat.clicked.connect(self._select_recommended_bloat)
        btn_row.addWidget(btn_select_bloat)

        btn_row.addStretch(1)

        self._btn_disable = QPushButton("Disable Selected")
        self._btn_disable.setIcon(get_icon("cross", 14))
        self._btn_disable.setToolTip("Disable package for user 0 (prevents background running)")
        self._btn_disable.clicked.connect(self._on_disable_clicked)
        btn_row.addWidget(self._btn_disable)

        self._btn_uninstall = QPushButton("Uninstall for User")
        self._btn_uninstall.setIcon(get_icon("trash", 14))
        self._btn_uninstall.setProperty("cssClass", "danger")
        self._btn_uninstall.setToolTip("Uninstall app from user space while keeping APK in system image for safety")
        self._btn_uninstall.clicked.connect(self._on_uninstall_clicked)
        btn_row.addWidget(self._btn_uninstall)

        self._btn_restore = QPushButton("Restore / Re-enable")
        self._btn_restore.setIcon(get_icon("refresh", 14))
        self._btn_restore.setProperty("cssClass", "primary")
        self._btn_restore.setToolTip("Restore or re-enable disabled/uninstalled system app")
        self._btn_restore.clicked.connect(self._on_restore_clicked)
        btn_row.addWidget(self._btn_restore)

        layout.addLayout(btn_row)

        # Debloater status label
        self._debloat_status = QLabel("Ready.")
        self._debloat_status.setProperty("cssClass", "muted")
        layout.addWidget(self._debloat_status)

        return tab

    # -------------------------------------------------------------------------
    # Tab 2: Hardware & Battery Health
    # -------------------------------------------------------------------------

    def _build_health_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Battery Group
        batt_group = QGroupBox("Battery & Power Subsystem")
        batt_layout = QGridLayout(batt_group)
        batt_layout.setSpacing(12)

        batt_layout.addWidget(QLabel("Battery Level:"), 0, 0)
        self._lbl_batt_level = QLabel("N/A")
        self._lbl_batt_level.setProperty("cssClass", "metric")
        batt_layout.addWidget(self._lbl_batt_level, 0, 1)

        batt_layout.addWidget(QLabel("Health Condition:"), 0, 2)
        self._lbl_batt_health = QLabel("N/A")
        self._lbl_batt_health.setProperty("cssClass", "metric")
        batt_layout.addWidget(self._lbl_batt_health, 0, 3)

        batt_layout.addWidget(QLabel("Voltage:"), 1, 0)
        self._lbl_batt_voltage = QLabel("N/A")
        self._lbl_batt_voltage.setProperty("cssClass", "metric")
        batt_layout.addWidget(self._lbl_batt_voltage, 1, 1)

        batt_layout.addWidget(QLabel("Temperature:"), 1, 2)
        self._lbl_batt_temp = QLabel("N/A")
        self._lbl_batt_temp.setProperty("cssClass", "metric")
        batt_layout.addWidget(self._lbl_batt_temp, 1, 3)

        batt_layout.addWidget(QLabel("Power Source:"), 2, 0)
        self._lbl_batt_source = QLabel("N/A")
        self._lbl_batt_source.setProperty("cssClass", "metric")
        batt_layout.addWidget(self._lbl_batt_source, 2, 1)

        batt_layout.addWidget(QLabel("Technology:"), 2, 2)
        self._lbl_batt_tech = QLabel("N/A")
        self._lbl_batt_tech.setProperty("cssClass", "metric")
        batt_layout.addWidget(self._lbl_batt_tech, 2, 3)

        batt_layout.addWidget(QLabel("Charge Cycle Count:"), 3, 0)
        self._lbl_batt_cycles = QLabel("N/A")
        self._lbl_batt_cycles.setProperty("cssClass", "metric")
        batt_layout.addWidget(self._lbl_batt_cycles, 3, 1)

        batt_layout.addWidget(QLabel("Charge Capacity (Counter):"), 3, 2)
        self._lbl_batt_charge = QLabel("N/A")
        self._lbl_batt_charge.setProperty("cssClass", "metric")
        batt_layout.addWidget(self._lbl_batt_charge, 3, 3)

        layout.addWidget(batt_group)

        # Hardware Platform Specs Group
        hw_group = QGroupBox("Hardware Platform & Thermals")
        hw_layout = QGridLayout(hw_group)
        hw_layout.setSpacing(12)

        hw_layout.addWidget(QLabel("Screen Resolution:"), 0, 0)
        self._lbl_hw_res = QLabel("N/A")
        self._lbl_hw_res.setProperty("cssClass", "metric")
        hw_layout.addWidget(self._lbl_hw_res, 0, 1)

        hw_layout.addWidget(QLabel("Screen Density:"), 0, 2)
        self._lbl_hw_dpi = QLabel("N/A")
        self._lbl_hw_dpi.setProperty("cssClass", "metric")
        hw_layout.addWidget(self._lbl_hw_dpi, 0, 3)

        hw_layout.addWidget(QLabel("CPU Cores:"), 1, 0)
        self._lbl_hw_cores = QLabel("N/A")
        self._lbl_hw_cores.setProperty("cssClass", "metric")
        hw_layout.addWidget(self._lbl_hw_cores, 1, 1)

        hw_layout.addWidget(QLabel("CPU Scaling Governor:"), 1, 2)
        self._lbl_hw_gov = QLabel("N/A")
        self._lbl_hw_gov.setProperty("cssClass", "metric")
        hw_layout.addWidget(self._lbl_hw_gov, 1, 3)

        hw_layout.addWidget(QLabel("Thermal Telemetry:"), 2, 0)
        self._lbl_hw_thermals = QLabel("N/A")
        self._lbl_hw_thermals.setProperty("cssClass", "metric")
        hw_layout.addWidget(self._lbl_hw_thermals, 2, 1, 1, 3)

        layout.addWidget(hw_group)

        # Refresh button
        btn_refresh_health = QPushButton("Refresh Diagnostics & Health Data")
        btn_refresh_health.setIcon(get_icon("refresh", 14))
        btn_refresh_health.setProperty("cssClass", "primary")
        btn_refresh_health.clicked.connect(self.refresh_health)
        layout.addWidget(btn_refresh_health)

        layout.addStretch(1)
        scroll.setWidget(container)
        return scroll

    # -------------------------------------------------------------------------
    # Tab 3: System Tweaks
    # -------------------------------------------------------------------------

    def _build_tweaks_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Animation Speeds
        anim_group = QGroupBox("Animation Speeds (Snappier UI)")
        anim_layout = QVBoxLayout(anim_group)
        anim_layout.setSpacing(10)

        anim_desc = QLabel("Modify window, transition, and animator duration scales for ultra-fast app switching.")
        anim_desc.setProperty("cssClass", "muted")
        anim_layout.addWidget(anim_desc)

        self._lbl_current_anims = QLabel("Current scales: Window 1.0x, Transition 1.0x, Animator 1.0x")
        self._lbl_current_anims.setProperty("cssClass", "metric")
        anim_layout.addWidget(self._lbl_current_anims)

        anim_btn_row = QHBoxLayout()
        anim_btn_row.setSpacing(8)

        btn_anim_0 = QPushButton("0.0x (Instant / No Animations)")
        btn_anim_0.clicked.connect(lambda: self._apply_animation_scale(0.0))
        anim_btn_row.addWidget(btn_anim_0)

        btn_anim_05 = QPushButton("0.5x (Fast & Smooth)")
        btn_anim_05.setProperty("cssClass", "primary")
        btn_anim_05.clicked.connect(lambda: self._apply_animation_scale(0.5))
        anim_btn_row.addWidget(btn_anim_05)

        btn_anim_1 = QPushButton("1.0x (Stock Default)")
        btn_anim_1.clicked.connect(lambda: self._apply_animation_scale(1.0))
        anim_btn_row.addWidget(btn_anim_1)

        anim_btn_row.addStretch(1)
        anim_layout.addLayout(anim_btn_row)
        layout.addWidget(anim_group)

        # Screen Density (DPI)
        dpi_group = QGroupBox("Display Density (DPI)")
        dpi_layout = QVBoxLayout(dpi_group)
        dpi_layout.setSpacing(10)

        dpi_desc = QLabel("Adjust display DPI scaling. Lower values allow more screen content, higher values enlarge icons.")
        dpi_desc.setProperty("cssClass", "muted")
        dpi_layout.addWidget(dpi_desc)

        dpi_controls = QHBoxLayout()
        dpi_controls.setSpacing(10)

        dpi_controls.addWidget(QLabel("Custom DPI (120 - 800):"))
        self._spin_dpi = QSpinBox()
        self._spin_dpi.setRange(120, 800)
        self._spin_dpi.setValue(420)
        self._spin_dpi.setFixedWidth(100)
        dpi_controls.addWidget(self._spin_dpi)

        btn_apply_dpi = QPushButton("Apply DPI")
        btn_apply_dpi.setIcon(get_icon("check", 14))
        btn_apply_dpi.setProperty("cssClass", "primary")
        btn_apply_dpi.clicked.connect(self._apply_dpi)
        dpi_controls.addWidget(btn_apply_dpi)

        btn_reset_dpi = QPushButton("Reset to Factory Default")
        btn_reset_dpi.setIcon(get_icon("refresh", 14))
        btn_reset_dpi.clicked.connect(self._reset_dpi)
        dpi_controls.addWidget(btn_reset_dpi)

        dpi_controls.addStretch(1)
        dpi_layout.addLayout(dpi_controls)
        layout.addWidget(dpi_group)

        # Wireless ADB
        wifi_group = QGroupBox("Wireless ADB (Port 5555)")
        wifi_layout = QVBoxLayout(wifi_group)
        wifi_layout.setSpacing(10)

        wifi_desc = QLabel("Switch ADB from USB to TCP/IP port 5555 so you can execute wireless commands without a cable.")
        wifi_desc.setProperty("cssClass", "muted")
        wifi_layout.addWidget(wifi_desc)

        wifi_btn_row = QHBoxLayout()
        wifi_btn_row.setSpacing(10)

        btn_enable_wifi = QPushButton("Enable Wireless ADB")
        btn_enable_wifi.setIcon(get_icon("flash", 14))
        btn_enable_wifi.setProperty("cssClass", "primary")
        btn_enable_wifi.clicked.connect(self._enable_wireless_adb)
        wifi_btn_row.addWidget(btn_enable_wifi)

        self._lbl_wifi_ip = QLabel("Connect Command: N/A")
        self._lbl_wifi_ip.setProperty("cssClass", "metric")
        wifi_btn_row.addWidget(self._lbl_wifi_ip, 1)

        btn_copy_cmd = QPushButton("Copy Command")
        btn_copy_cmd.setIcon(get_icon("copy", 14))
        btn_copy_cmd.clicked.connect(self._copy_wireless_cmd)
        wifi_btn_row.addWidget(btn_copy_cmd)

        wifi_layout.addLayout(wifi_btn_row)
        layout.addWidget(wifi_group)

        # Stay Awake
        awake_group = QGroupBox("Developer Display Settings")
        awake_layout = QVBoxLayout(awake_group)
        self._chk_stay_awake = QCheckBox("Keep screen awake while charging (Stay Awake)")
        self._chk_stay_awake.toggled.connect(self._toggle_stay_awake)
        awake_layout.addWidget(self._chk_stay_awake)
        layout.addWidget(awake_group)

        # Tweaks status
        self._tweaks_status = QLabel("Ready.")
        self._tweaks_status.setProperty("cssClass", "muted")
        layout.addWidget(self._tweaks_status)

        layout.addStretch(1)
        scroll.setWidget(container)
        return scroll

    # =========================================================================
    # Device State Binding & Refresh
    # =========================================================================

    def load_for_device(self, device: Optional[DeviceInfo]) -> None:
        """Bind screen to active device and load diagnostics data."""
        self._current_device = device
        if not device or device.mode == "not_connected":
            self._device_badge.setText("No device connected")
            self._device_badge.setProperty("cssClass", "secondary")
            self._device_badge.setStyleSheet("padding: 5px 12px; font-size: 12px;")
            self._clear_all_views()
            return

        serial = device.serial
        summary = f"{device.brand.upper()} {device.model} ({serial}) [{device.mode.upper()}]"
        self._device_badge.setText(summary)
        self._device_badge.setProperty("cssClass", "subheading")
        self._device_badge.setStyleSheet("padding: 5px 12px; font-size: 12px; font-weight: 600;")

        if device.mode == "adb":
            self.refresh_packages()
            self.refresh_health()
            self.refresh_tweaks()
        else:
            self._debloat_status.setText(f"ADB mode required (Device is in {device.mode} mode).")
            self._tweaks_status.setText(f"ADB mode required (Device is in {device.mode} mode).")

    def _clear_all_views(self) -> None:
        self._cached_packages = []
        self._pkg_table.setRowCount(0)
        self._lbl_batt_level.setText("N/A")
        self._lbl_batt_health.setText("N/A")
        self._lbl_batt_voltage.setText("N/A")
        self._lbl_batt_temp.setText("N/A")
        self._lbl_batt_source.setText("N/A")
        self._lbl_batt_tech.setText("N/A")
        self._lbl_batt_cycles.setText("N/A")
        self._lbl_batt_charge.setText("N/A")
        self._lbl_hw_res.setText("N/A")
        self._lbl_hw_dpi.setText("N/A")
        self._lbl_hw_cores.setText("N/A")
        self._lbl_hw_gov.setText("N/A")
        self._lbl_hw_thermals.setText("N/A")
        self._lbl_wifi_ip.setText("Connect Command: N/A")
        self._debloat_status.setText("Connect an ADB device to inspect packages.")
        self._tweaks_status.setText("Connect an ADB device to apply tweaks.")

    # =========================================================================
    # Debloater Logic
    # =========================================================================

    def refresh_packages(self) -> None:
        serial = self._current_device.serial if self._current_device else ""
        if not serial:
            self._debloat_status.setText("No active device serial.")
            return

        self._debloat_status.setText("Enumerating installed packages...")
        try:
            self._cached_packages = self._debloater.list_packages(serial=serial)
            self._apply_package_filter()
            bloat_count = sum(1 for p in self._cached_packages if p.category in ("bloat", "carrier"))
            self._debloat_status.setText(
                f"Loaded {len(self._cached_packages)} packages ({bloat_count} potential bloat/carrier apps)."
            )
        except Exception as exc:
            log.error("Failed to list packages: %s", exc)
            self._debloat_status.setText(f"Error loading packages: {exc}")

    def _apply_package_filter(self) -> None:
        search = self._search_input.text().strip().lower()
        cat_idx = self._category_combo.currentIndex()
        state_idx = self._state_combo.currentIndex()

        filtered: list[InstalledPackage] = []
        for p in self._cached_packages:
            # Search filter
            if search and search not in p.package_name.lower() and search not in p.label.lower():
                continue

            # Category filter
            if cat_idx == 1 and p.category != "bloat":
                continue
            elif cat_idx == 2 and p.category != "carrier":
                continue
            elif cat_idx == 3 and p.category != "user":
                continue
            elif cat_idx == 4 and p.category != "system":
                continue
            elif cat_idx == 5 and p.category != "protected":
                continue

            # State filter
            if state_idx == 1 and not p.is_enabled:
                continue
            elif state_idx == 2 and p.is_enabled:
                continue

            filtered.append(p)

        self._populate_package_table(filtered)

    def _populate_package_table(self, packages: list[InstalledPackage]) -> None:
        self._pkg_table.setRowCount(0)
        self._pkg_table.setSortingEnabled(False)

        for row, p in enumerate(packages):
            self._pkg_table.insertRow(row)

            # Column 0: Package Name
            item_pkg = QTableWidgetItem(p.package_name)
            item_pkg.setData(Qt.ItemDataRole.UserRole, p.package_name)
            self._pkg_table.setItem(row, 0, item_pkg)

            # Column 1: Label
            item_label = QTableWidgetItem(p.label)
            self._pkg_table.setItem(row, 1, item_label)

            # Column 2: Category
            item_cat = QTableWidgetItem(p.category.upper())
            if p.category == "bloat":
                item_cat.setForeground(Qt.GlobalColor.yellow)
            elif p.category == "carrier":
                item_cat.setForeground(Qt.GlobalColor.cyan)
            elif p.category == "protected":
                item_cat.setForeground(Qt.GlobalColor.red)
            self._pkg_table.setItem(row, 2, item_cat)

            # Column 3: Status
            status_text = "Enabled" if p.is_enabled else "Disabled"
            item_status = QTableWidgetItem(status_text)
            item_status.setForeground(Qt.GlobalColor.green if p.is_enabled else Qt.GlobalColor.gray)
            self._pkg_table.setItem(row, 3, item_status)

        self._pkg_table.setSortingEnabled(True)

    def _get_selected_packages(self) -> list[str]:
        selected_rows = {index.row() for index in self._pkg_table.selectedIndexes()}
        packages: list[str] = []
        for row in selected_rows:
            item = self._pkg_table.item(row, 0)
            if item:
                packages.append(item.text().strip())
        return packages

    def _select_recommended_bloat(self) -> None:
        self._pkg_table.clearSelection()
        for row in range(self._pkg_table.rowCount()):
            cat_item = self._pkg_table.item(row, 2)
            if cat_item and cat_item.text().lower() in ("bloat", "carrier"):
                self._pkg_table.selectRow(row)

    def _on_disable_clicked(self) -> None:
        pkgs = self._get_selected_packages()
        if not pkgs:
            QMessageBox.information(self, "No Selection", "Please select at least one package from the table.")
            return

        # Check protected packages
        protected = [p for p in pkgs if p in CRITICAL_PROTECTED_PACKAGES]
        if protected:
            QMessageBox.warning(
                self,
                "Protected System Package",
                f"The following packages are essential for Android system stability and cannot be disabled:\n\n"
                + "\n".join(protected),
            )
            pkgs = [p for p in pkgs if p not in CRITICAL_PROTECTED_PACKAGES]
            if not pkgs:
                return

        reply = QMessageBox.question(
            self,
            "Disable Packages?",
            f"Are you sure you want to disable {len(pkgs)} selected package(s)?\n"
            "This will freeze them for user 0 without deleting application data.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        serial = self._current_device.serial if self._current_device else ""
        success_count = 0
        for p in pkgs:
            ok, _ = self._debloater.disable_package(p, serial=serial)
            if ok:
                success_count += 1

        self._debloat_status.setText(f"Disabled {success_count}/{len(pkgs)} packages.")
        self.refresh_packages()

    def _on_uninstall_clicked(self) -> None:
        pkgs = self._get_selected_packages()
        if not pkgs:
            QMessageBox.information(self, "No Selection", "Please select at least one package to uninstall.")
            return

        protected = [p for p in pkgs if p in CRITICAL_PROTECTED_PACKAGES]
        if protected:
            QMessageBox.warning(
                self,
                "Protected Package",
                f"The following packages cannot be uninstalled:\n\n" + "\n".join(protected),
            )
            pkgs = [p for p in pkgs if p not in CRITICAL_PROTECTED_PACKAGES]
            if not pkgs:
                return

        reply = QMessageBox.question(
            self,
            "Confirm Package Uninstallation",
            f"Uninstall {len(pkgs)} package(s) for the current user?\n\n"
            "FlashDock uses 'pm uninstall -k --user 0', which keeps the APK on the system partition "
            "so you can easily restore it anytime via the 'Restore / Re-enable' button.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        serial = self._current_device.serial if self._current_device else ""
        success_count = 0
        for p in pkgs:
            ok, _ = self._debloater.uninstall_package(p, serial=serial)
            if ok:
                success_count += 1

        self._debloat_status.setText(f"Uninstalled {success_count}/{len(pkgs)} packages for user 0.")
        self.refresh_packages()

    def _on_restore_clicked(self) -> None:
        pkgs = self._get_selected_packages()
        if not pkgs:
            QMessageBox.information(self, "No Selection", "Select a package to restore/reinstall.")
            return

        serial = self._current_device.serial if self._current_device else ""
        success_count = 0
        for p in pkgs:
            ok, _ = self._debloater.restore_package(p, serial=serial)
            if ok:
                success_count += 1

        self._debloat_status.setText(f"Restored {success_count}/{len(pkgs)} packages.")
        self.refresh_packages()

    # =========================================================================
    # Health & Hardware Logic
    # =========================================================================

    def refresh_health(self) -> None:
        serial = self._current_device.serial if self._current_device else ""
        if not serial:
            return

        try:
            batt = self._health_inspector.get_battery_health(serial=serial)
            specs = self._health_inspector.get_hardware_specs(serial=serial)

            self._lbl_batt_level.setText(f"{batt.level}%" if batt.level >= 0 else "Unknown")
            self._lbl_batt_health.setText(batt.health_status)
            self._lbl_batt_voltage.setText(f"{batt.voltage_mv} mV")
            self._lbl_batt_temp.setText(f"{batt.temperature_c} °C")
            self._lbl_batt_source.setText(batt.power_source)
            self._lbl_batt_tech.setText(batt.technology)
            self._lbl_batt_cycles.setText(str(batt.cycle_count) if batt.cycle_count is not None else "N/A (Driver Not Exposed)")
            self._lbl_batt_charge.setText(f"{batt.charge_counter_uah} µAh" if batt.charge_counter_uah else "N/A")

            self._lbl_hw_res.setText(specs.resolution)
            self._lbl_hw_dpi.setText(specs.density_dpi)
            self._lbl_hw_cores.setText(f"{specs.cpu_cores} Cores")
            self._lbl_hw_gov.setText(specs.cpu_governor)
            self._lbl_hw_thermals.setText(", ".join(specs.thermal_zones) if specs.thermal_zones else "SOC Normal")

        except Exception as exc:
            log.error("Failed to query hardware telemetry: %s", exc)

    # =========================================================================
    # Tweaks Logic
    # =========================================================================

    def refresh_tweaks(self) -> None:
        serial = self._current_device.serial if self._current_device else ""
        if not serial:
            return

        try:
            scales = self._tweaker.get_animation_scales(serial=serial)
            w = scales.get("window", 1.0)
            t = scales.get("transition", 1.0)
            a = scales.get("animator", 1.0)
            self._lbl_current_anims.setText(f"Current scales: Window {w}x, Transition {t}x, Animator {a}x")
        except Exception as exc:
            log.error("Failed to query animation scales: %s", exc)

    def _apply_animation_scale(self, scale: float) -> None:
        serial = self._current_device.serial if self._current_device else ""
        if not serial:
            return
        ok, msg = self._tweaker.set_animation_scales(scale, serial=serial)
        self._tweaks_status.setText(msg)
        self.refresh_tweaks()

    def _apply_dpi(self) -> None:
        serial = self._current_device.serial if self._current_device else ""
        if not serial:
            return
        dpi = self._spin_dpi.value()
        ok, msg = self._tweaker.set_screen_density(dpi, serial=serial)
        self._tweaks_status.setText(msg)
        self.refresh_health()

    def _reset_dpi(self) -> None:
        serial = self._current_device.serial if self._current_device else ""
        if not serial:
            return
        ok, msg = self._tweaker.reset_screen_density(serial=serial)
        self._tweaks_status.setText(msg)
        self.refresh_health()

    def _enable_wireless_adb(self) -> None:
        serial = self._current_device.serial if self._current_device else ""
        if not serial:
            return
        ok, msg = self._tweaker.enable_wireless_adb(serial=serial)
        self._tweaks_status.setText(msg)

        m = re.search(r"(adb connect [\d\.\:]+)", msg)
        if m:
            self._lbl_wifi_ip.setText(m.group(1))
        else:
            self._lbl_wifi_ip.setText("Port 5555 opened. Connect via adb connect <phone_ip>:5555")

    def _copy_wireless_cmd(self) -> None:
        txt = self._lbl_wifi_ip.text().strip()
        if "adb connect" in txt:
            cmd = txt.split(":")[-1].strip() if ":" in txt and not txt.startswith("adb") else txt
            QApplication.clipboard().setText(cmd)
            self._tweaks_status.setText("Copied connection command to clipboard!")
        else:
            QMessageBox.information(self, "No IP", "Enable wireless ADB first to obtain the connect command.")

    def _toggle_stay_awake(self, checked: bool) -> None:
        serial = self._current_device.serial if self._current_device else ""
        if not serial:
            return
        ok, msg = self._tweaker.set_stay_awake(checked, serial=serial)
        self._tweaks_status.setText(msg)
