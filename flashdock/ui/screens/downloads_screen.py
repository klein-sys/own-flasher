"""
FlashDock — Downloads, Drivers & Tools Manager Screen (Phase 12).

Provides a modern Apple HIG / macOS Big Sur 3-tab workstation for:
1. Platform-Tools (ADB & Fastboot) verification, daemon restart, and 1-click official Google updates.
2. OEM USB Drivers (Google, Samsung, Xiaomi, MTK VCOM, Qualcomm 9008 EDL) with PnP diagnostics.
3. Official Firmware, GSI & Recovery portals finder with codename auto-matching.
"""

from __future__ import annotations

import os
from pathlib import Path
import threading
from typing import Optional

from PySide6.QtCore import Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from flashdock.constants import DRIVERS_DIR, GSIS_DIR, ROMS_DIR, TOOLS_DIR
from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.core.tools_manager import (
    DriverManager,
    DriverPackage,
    FirmwareFinder,
    FirmwareRepo,
    PlatformToolsManager,
    ToolInfo,
)
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot
from flashdock.tools.scrcpy import ScrcpyManager
from flashdock.ui.icon_assets import create_icon_label, get_icon
from flashdock.ui.widgets.scrcpy_dialog import ScrcpyDialog

log = get_logger(__name__)


class DownloadsScreen(QWidget):
    """Downloads, Drivers & Platform-Tools Management Screen."""

    # Thread-safe UI update signals
    progress_updated = Signal(int, int)  # current, total
    download_finished = Signal(bool, str)
    status_message_updated = Signal(str)

    def __init__(
        self,
        device_mgr: Optional[DeviceManager] = None,
        adb: Optional[ADB] = None,
        fastboot: Optional[Fastboot] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._device_mgr = device_mgr
        self._adb = adb or ADB()
        self._fastboot = fastboot or Fastboot()

        self._tools_mgr = PlatformToolsManager(adb=self._adb, fastboot=self._fastboot)
        self._driver_mgr = DriverManager()
        self._scrcpy_mgr = ScrcpyManager(tools_dir=TOOLS_DIR)
        self._firmware_finder = FirmwareFinder()

        self._current_device: Optional[DeviceInfo] = None
        self._active_worker: Optional[threading.Thread] = None

        self._build_ui()
        self._connect_internal_signals()
        self.refresh_tools_status()

    # -------------------------------------------------------------------------
    # UI Construction
    # -------------------------------------------------------------------------

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 20, 24, 20)
        root_layout.setSpacing(16)

        # ---- Header Row ----
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        t_row = QHBoxLayout()
        t_row.setSpacing(8)
        t_row.addWidget(create_icon_label("downloads", 22))
        title = QLabel("Downloads, Drivers & Tools Manager")
        title.setProperty("cssClass", "heading")
        t_row.addWidget(title)
        t_row.addStretch()
        title_col.addLayout(t_row)

        subtitle = QLabel(
            "Manage official platform-tools, install OEM USB drivers, and browse stock firmware repositories."
        )
        subtitle.setProperty("cssClass", "muted")
        title_col.addWidget(subtitle)
        header_row.addLayout(title_col, 1)

        # Device Indicator Badge
        self._device_badge = QLabel("No device connected")
        self._device_badge.setStyleSheet(
            "background-color: #242426; border: 1px solid #38383A; "
            "border-radius: 6px; padding: 6px 12px; font-size: 12px; color: #8E8E93;"
        )
        header_row.addWidget(self._device_badge)

        root_layout.addLayout(header_row)

        # ---- Main 3-Tab Widget ----
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_tools_tab(), get_icon("tools", 16), "Platform-Tools & Daemon")
        self._tabs.addTab(self._build_drivers_tab(), get_icon("usb", 16), "OEM USB Drivers & Fixer")
        self._tabs.addTab(self._build_firmware_tab(), get_icon("downloads", 16), "Official Firmware & GSI Repos")
        root_layout.addWidget(self._tabs, 1)

        # ---- Global Download Progress Bar ----
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setRange(0, 100)
        root_layout.addWidget(self._progress_bar)

        self._status_label = QLabel("Ready")
        self._status_label.setProperty("cssClass", "muted")
        root_layout.addWidget(self._status_label)

    # -------------------------------------------------------------------------
    # Tab 1: Platform-Tools & Daemon
    # -------------------------------------------------------------------------

    def _build_tools_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Status Cards Container
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        # ADB Status Card
        self._adb_card = QFrame()
        self._adb_card.setProperty("cssClass", "card")
        adb_box = QVBoxLayout(self._adb_card)
        adb_box.setSpacing(6)

        adb_h_row = QHBoxLayout()
        adb_h_row.setSpacing(6)
        adb_h_row.addWidget(create_icon_label("terminal", 16))
        adb_header = QLabel("ADB (Android Debug Bridge)")
        adb_header.setProperty("cssClass", "subheading")
        adb_h_row.addWidget(adb_header)
        adb_h_row.addStretch()
        adb_box.addLayout(adb_h_row)

        self._adb_status_text = QLabel("Checking ADB...")
        self._adb_status_text.setWordWrap(True)
        adb_box.addWidget(self._adb_status_text)
        cards_layout.addWidget(self._adb_card, 1)

        # Fastboot Status Card
        self._fb_card = QFrame()
        self._fb_card.setProperty("cssClass", "card")
        fb_box = QVBoxLayout(self._fb_card)
        fb_box.setSpacing(6)

        fb_h_row = QHBoxLayout()
        fb_h_row.setSpacing(6)
        fb_h_row.addWidget(create_icon_label("flash", 16))
        fb_header = QLabel("Fastboot")
        fb_header.setProperty("cssClass", "subheading")
        fb_h_row.addWidget(fb_header)
        fb_h_row.addStretch()
        fb_box.addLayout(fb_h_row)

        self._fb_status_text = QLabel("Checking Fastboot...")
        self._fb_status_text.setWordWrap(True)
        fb_box.addWidget(self._fb_status_text)
        cards_layout.addWidget(self._fb_card, 1)

        # scrcpy Screen Mirror Status Card
        self._scrcpy_card = QFrame()
        self._scrcpy_card.setProperty("cssClass", "card")
        scrcpy_box = QVBoxLayout(self._scrcpy_card)
        scrcpy_box.setSpacing(6)

        scrcpy_h_row = QHBoxLayout()
        scrcpy_h_row.setSpacing(6)
        scrcpy_h_row.addWidget(create_icon_label("scrcpy", 16))
        scrcpy_header = QLabel("scrcpy Screen Mirror")
        scrcpy_header.setProperty("cssClass", "subheading")
        scrcpy_h_row.addWidget(scrcpy_header)
        scrcpy_h_row.addStretch()
        scrcpy_box.addLayout(scrcpy_h_row)

        self._scrcpy_status_text = QLabel("Checking scrcpy...")
        self._scrcpy_status_text.setWordWrap(True)
        scrcpy_box.addWidget(self._scrcpy_status_text)

        scrcpy_btn_row = QHBoxLayout()
        scrcpy_btn_row.setSpacing(6)

        self._btn_launch_scrcpy = QPushButton("Mirror Screen")
        self._btn_launch_scrcpy.setIcon(get_icon("scrcpy", 16))
        self._btn_launch_scrcpy.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_launch_scrcpy.setProperty("cssClass", "primary")
        self._btn_launch_scrcpy.clicked.connect(self._on_launch_scrcpy)
        scrcpy_btn_row.addWidget(self._btn_launch_scrcpy)

        self._btn_download_scrcpy = QPushButton("Get scrcpy")
        self._btn_download_scrcpy.setIcon(get_icon("downloads", 16))
        self._btn_download_scrcpy.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_download_scrcpy.clicked.connect(self._on_download_scrcpy)
        scrcpy_btn_row.addWidget(self._btn_download_scrcpy)

        scrcpy_box.addLayout(scrcpy_btn_row)
        cards_layout.addWidget(self._scrcpy_card, 1)

        layout.addLayout(cards_layout)

        # Platform-Tools Controls Group
        actions_group = QGroupBox("Platform-Tools Actions")
        actions_layout = QHBoxLayout(actions_group)
        actions_layout.setSpacing(10)

        self._btn_verify_tools = QPushButton("Verify & Check Versions")
        self._btn_verify_tools.setIcon(get_icon("refresh", 16))
        self._btn_verify_tools.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_verify_tools.clicked.connect(self.refresh_tools_status)
        actions_layout.addWidget(self._btn_verify_tools)

        self._btn_restart_adb = QPushButton("Restart ADB Daemon")
        self._btn_restart_adb.setIcon(get_icon("refresh", 16))
        self._btn_restart_adb.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_restart_adb.setToolTip("Kill ADB server and start a fresh server instance")
        self._btn_restart_adb.clicked.connect(self._on_restart_adb_daemon)
        actions_layout.addWidget(self._btn_restart_adb)

        self._btn_download_pt = QPushButton("Download Google Platform-Tools")
        self._btn_download_pt.setIcon(get_icon("downloads", 16))
        self._btn_download_pt.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_download_pt.setProperty("cssClass", "primary")
        self._btn_download_pt.setToolTip("Download and install official platform-tools directly from Google")
        self._btn_download_pt.clicked.connect(self._on_download_platform_tools)
        actions_layout.addWidget(self._btn_download_pt)

        self._btn_open_pt_dir = QPushButton("Open Tools Folder")
        self._btn_open_pt_dir.setIcon(get_icon("folder", 16))
        self._btn_open_pt_dir.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_open_pt_dir.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(TOOLS_DIR))))
        actions_layout.addWidget(self._btn_open_pt_dir)

        layout.addWidget(actions_group)

        # Informational Note
        info_frame = QFrame()
        info_frame.setProperty("cssClass", "card_subtle")
        info_layout = QVBoxLayout(info_frame)
        info_h_row = QHBoxLayout()
        info_h_row.setSpacing(6)
        info_h_row.addWidget(create_icon_label("info", 16))
        info_title = QLabel("Platform-Tools Architecture & Port Information")
        info_title.setStyleSheet("font-weight: 600; font-size: 13px; color: #0A84FF;")
        info_h_row.addWidget(info_title)
        info_h_row.addStretch()
        info_layout.addLayout(info_h_row)
        info_desc = QLabel(
            "• FlashDock communicates with Android devices via standard TCP port 5037 (ADB Daemon).\n"
            "• If your device is connected but not recognized, ensure USB Debugging is ON and click 'Restart ADB Daemon'.\n"
            "• Platform-tools binaries are isolated in the local data directory without cluttering global system PATH."
        )
        info_desc.setProperty("cssClass", "muted")
        info_layout.addWidget(info_desc)
        layout.addWidget(info_frame)

        layout.addStretch(1)
        return tab

    # -------------------------------------------------------------------------
    # Tab 2: OEM USB Drivers & Fixer
    # -------------------------------------------------------------------------

    def _build_drivers_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Device Suggestion & Troubleshooter Banner
        banner_row = QHBoxLayout()
        banner_row.setSpacing(10)

        self._driver_suggestion_lbl = QLabel(
            "Plug in your device to get targeted driver recommendations."
        )
        self._driver_suggestion_lbl.setProperty("cssClass", "card_subtle")
        banner_row.addWidget(self._driver_suggestion_lbl, 1)

        btn_scan_pnp = QPushButton("Scan Windows for Driver Errors")
        btn_scan_pnp.setIcon(get_icon("search", 16))
        btn_scan_pnp.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_scan_pnp.setToolTip("Scan Windows Device Manager for Android devices in yellow warning state")
        btn_scan_pnp.clicked.connect(self._on_scan_pnp_devices)
        banner_row.addWidget(btn_scan_pnp)

        btn_open_drivers = QPushButton("Open Drivers Folder")
        btn_open_drivers.setIcon(get_icon("folder", 16))
        btn_open_drivers.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open_drivers.setToolTip("Open local drivers storage folder")
        btn_open_drivers.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(DRIVERS_DIR))))
        banner_row.addWidget(btn_open_drivers)

        btn_install_file = QPushButton("Install Driver from File (.inf / .zip / .exe)")
        btn_install_file.setIcon(get_icon("plus", 16))
        btn_install_file.setProperty("cssClass", "primary")
        btn_install_file.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_install_file.setToolTip("Browse and install ANY driver file (.inf, .zip, .exe, .msi) from your computer")
        btn_install_file.clicked.connect(self._on_install_driver_from_file)
        banner_row.addWidget(btn_install_file)

        layout.addLayout(banner_row)

        # Scrollable Drivers Cards List
        self._drivers_scroll = QScrollArea()
        self._drivers_scroll.setWidgetResizable(True)
        self._drivers_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._drivers_container = QWidget()
        self._drivers_layout = QVBoxLayout(self._drivers_container)
        self._drivers_layout.setSpacing(12)
        self._drivers_layout.setContentsMargins(0, 0, 0, 0)

        self._drivers_scroll.setWidget(self._drivers_container)
        layout.addWidget(self._drivers_scroll, 1)

        self._refresh_drivers_cards()
        return tab

    # -------------------------------------------------------------------------
    # Tab 3: Official Firmware & GSI Finder
    # -------------------------------------------------------------------------

    def _build_firmware_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Filter & Search Controls
        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        self._fw_search_input = QLineEdit()
        self._fw_search_input.setPlaceholderText("Search firmware repositories, brand, or codename (e.g. Pixel, Xiaomi, GSI)...")
        self._fw_search_input.textChanged.connect(self._filter_firmware_cards)
        filter_row.addWidget(self._fw_search_input, 1)

        # Category Buttons
        self._fw_cat_btn_all = QPushButton("All")
        self._fw_cat_btn_all.setCheckable(True)
        self._fw_cat_btn_all.setChecked(True)
        self._fw_cat_btn_all.clicked.connect(lambda: self._set_fw_category("all"))
        filter_row.addWidget(self._fw_cat_btn_all)

        self._fw_cat_btn_factory = QPushButton("Factory Images")
        self._fw_cat_btn_factory.setCheckable(True)
        self._fw_cat_btn_factory.clicked.connect(lambda: self._set_fw_category("factory"))
        filter_row.addWidget(self._fw_cat_btn_factory)

        self._fw_cat_btn_gsi = QPushButton("GSIs")
        self._fw_cat_btn_gsi.setCheckable(True)
        self._fw_cat_btn_gsi.clicked.connect(lambda: self._set_fw_category("gsi"))
        filter_row.addWidget(self._fw_cat_btn_gsi)

        self._fw_cat_btn_rec = QPushButton("Recoveries")
        self._fw_cat_btn_rec.setCheckable(True)
        self._fw_cat_btn_rec.clicked.connect(lambda: self._set_fw_category("recovery"))
        filter_row.addWidget(self._fw_cat_btn_rec)

        layout.addLayout(filter_row)

        # Scrollable Repositories List
        self._fw_scroll = QScrollArea()
        self._fw_scroll.setWidgetResizable(True)
        self._fw_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._fw_cards_container = QWidget()
        self._fw_cards_layout = QVBoxLayout(self._fw_cards_container)
        self._fw_cards_layout.setSpacing(10)
        self._fw_cards_layout.setContentsMargins(0, 0, 0, 0)

        self._fw_scroll.setWidget(self._fw_cards_container)
        layout.addWidget(self._fw_scroll, 1)

        self._active_fw_category = "all"
        self._populate_firmware_cards()

        # Bottom Quick Storage Buttons
        quick_row = QHBoxLayout()
        quick_row.setSpacing(10)
        btn_open_roms = QPushButton("Open Local ROMs Folder (data/roms/)")
        btn_open_roms.setIcon(get_icon("folder", 16))
        btn_open_roms.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open_roms.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(ROMS_DIR))))
        quick_row.addWidget(btn_open_roms)

        btn_open_gsis = QPushButton("Open Local GSIs Folder (data/gsis/)")
        btn_open_gsis.setIcon(get_icon("folder", 16))
        btn_open_gsis.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open_gsis.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(GSIS_DIR))))
        quick_row.addWidget(btn_open_gsis)

        layout.addLayout(quick_row)
        return tab

    # -------------------------------------------------------------------------
    # Signals & Slots Wiring
    # -------------------------------------------------------------------------

    def _connect_internal_signals(self) -> None:
        self.progress_updated.connect(self._handle_progress_update)
        self.download_finished.connect(self._handle_download_finished)
        self.status_message_updated.connect(self._handle_status_message)

    @Slot(int, int)
    def _handle_progress_update(self, current: int, total: int) -> None:
        if total > 0:
            pct = int((current / total) * 100)
            self._progress_bar.setVisible(True)
            self._progress_bar.setValue(pct)
            cur_mb = round(current / (1024 * 1024), 1)
            tot_mb = round(total / (1024 * 1024), 1)
            self._status_label.setText(f"Downloading: {cur_mb} MB / {tot_mb} MB ({pct}%)")
        else:
            self._progress_bar.setVisible(True)
            cur_mb = round(current / (1024 * 1024), 1)
            self._status_label.setText(f"Downloading: {cur_mb} MB...")

    @Slot(bool, str)
    def _handle_download_finished(self, success: bool, message: str) -> None:
        self._progress_bar.setVisible(False)
        self._status_label.setText(message)
        self.refresh_tools_status()
        self._refresh_drivers_table()

        if success:
            QMessageBox.information(self, "Completed", message)
        else:
            QMessageBox.warning(self, "Download / Install Error", message)

    @Slot(str)
    def _handle_status_message(self, message: str) -> None:
        self._status_label.setText(message)

    # -------------------------------------------------------------------------
    # Logic: Tools Tab
    # -------------------------------------------------------------------------

    @Slot()
    def refresh_tools_status(self) -> None:
        """Inspect and refresh ADB, Fastboot, and scrcpy status indicators."""
        status = self._tools_mgr.check_status()
        adb_info = status["adb"]
        fb_info = status["fastboot"]

        # Update ADB Card
        if adb_info.status == "ready":
            self._adb_status_text.setText(
                f"<b>Ready</b><br>"
                f"Version: <code>{adb_info.version}</code><br>"
                f"Path: <small>{adb_info.binary_path}</small>"
            )
        else:
            self._adb_status_text.setText(
                "<b>Missing</b><br>ADB binary not found on system. Click 'Download Google Platform-Tools'."
            )

        # Update Fastboot Card
        if fb_info.status == "ready":
            self._fb_status_text.setText(
                f"<b>Ready</b><br>"
                f"Version: <code>{fb_info.version}</code><br>"
                f"Path: <small>{fb_info.binary_path}</small>"
            )
        else:
            self._fb_status_text.setText(
                "<b>Missing</b><br>Fastboot binary not found. Click 'Download Google Platform-Tools'."
            )

        # Update scrcpy Card
        if hasattr(self, "_scrcpy_status_text") and hasattr(self, "_scrcpy_mgr"):
            if self._scrcpy_mgr.is_installed():
                scrcpy_exe = self._scrcpy_mgr.get_executable()
                scrcpy_ver = self._scrcpy_mgr.get_version()
                self._scrcpy_status_text.setText(
                    f"<b>Ready</b><br>"
                    f"Version: <code>{scrcpy_ver}</code><br>"
                    f"Path: <small>{scrcpy_exe}</small>"
                )
                if hasattr(self, "_btn_launch_scrcpy"):
                    self._btn_launch_scrcpy.setEnabled(True)
                if hasattr(self, "_btn_download_scrcpy"):
                    self._btn_download_scrcpy.setText("Update")
                    self._btn_download_scrcpy.setIcon(get_icon("refresh", 16))
            else:
                self._scrcpy_status_text.setText(
                    "<b>Not Installed</b><br>Screen mirroring binary not found. Click 'Get scrcpy'."
                )
                if hasattr(self, "_btn_launch_scrcpy"):
                    self._btn_launch_scrcpy.setEnabled(False)
                if hasattr(self, "_btn_download_scrcpy"):
                    self._btn_download_scrcpy.setText("Get scrcpy")
                    self._btn_download_scrcpy.setIcon(get_icon("downloads", 16))

    @Slot()
    def _on_launch_scrcpy(self) -> None:
        """Launch the scrcpy configuration dialog."""
        adb_p = Path(self._adb.binary_path) if self._adb.binary_path else None
        dlg = ScrcpyDialog(
            manager=self._scrcpy_mgr,
            device=self._current_device,
            adb_path=adb_p,
            parent=self,
        )
        dlg.exec()

    @Slot()
    def _on_download_scrcpy(self) -> None:
        """Download latest official scrcpy Windows bundle."""
        if self._active_worker and self._active_worker.is_alive():
            QMessageBox.information(self, "Busy", "A download operation is already running.")
            return

        def _worker():
            def _prog(cur, tot):
                self.progress_updated.emit(cur, tot)

            success, msg = self._scrcpy_mgr.download_and_install(progress_callback=_prog)
            self.download_finished.emit(success, msg)

        self._active_worker = threading.Thread(target=_worker, daemon=True)
        self._active_worker.start()
        self._status_label.setText("Downloading official Genymobile scrcpy...")

    @Slot()
    def _on_restart_adb_daemon(self) -> None:
        """Restart ADB server."""
        self._status_label.setText("Restarting ADB daemon...")
        success, msg = self._tools_mgr.restart_adb_daemon()
        self._status_label.setText(msg)
        if success:
            QMessageBox.information(self, "ADB Daemon", "ADB daemon restarted successfully.")
        else:
            QMessageBox.warning(self, "ADB Daemon", f"Could not restart ADB daemon:\n{msg}")

    @Slot()
    def _on_download_platform_tools(self) -> None:
        """Asynchronously download and install Google platform-tools."""
        if self._active_worker and self._active_worker.is_alive():
            QMessageBox.information(self, "Busy", "A download operation is already running.")
            return

        reply = QMessageBox.question(
            self,
            "Download Platform-Tools",
            "Download the latest official Android Platform-Tools (ADB & Fastboot) from Google?\n\n"
            "This will download ~15 MB and install to FlashDock data directory.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        def _worker():
            def _prog(cur, tot):
                self.progress_updated.emit(cur, tot)

            success, msg = self._tools_mgr.download_and_install_platform_tools(progress_callback=_prog)
            self.download_finished.emit(success, msg)

        self._active_worker = threading.Thread(target=_worker, daemon=True)
        self._active_worker.start()
        self._status_label.setText("Downloading official Google platform-tools...")

    # -------------------------------------------------------------------------
    # Logic: Drivers Tab
    # -------------------------------------------------------------------------

    def _refresh_drivers_cards(self) -> None:
        """Populate the OEM USB Drivers cards with spacious, clean buttons."""
        while self._drivers_layout.count():
            item = self._drivers_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        drivers = self._driver_mgr.get_all_drivers()
        for drv in drivers:
            card = self._make_driver_card(drv)
            self._drivers_layout.addWidget(card)

        self._drivers_layout.addStretch(1)

    _refresh_drivers_table = _refresh_drivers_cards

    def _make_driver_card(self, drv: DriverPackage) -> QFrame:
        card = QFrame()
        card.setProperty("cssClass", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        # Header: Name & Status
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        top_row.addWidget(create_icon_label("usb", 16))
        name_lbl = QLabel(drv.name)
        name_lbl.setProperty("cssClass", "subheading")
        top_row.addWidget(name_lbl, 1)

        status_text = "Ready" if drv.is_installed else ("Downloaded" if drv.is_downloaded else "Available")
        status_color = "#30D158" if drv.is_installed else ("#0A84FF" if drv.is_downloaded else "#8E8E93")
        status_lbl = QLabel(f" {status_text} ")
        status_lbl.setStyleSheet(
            f"background-color: rgba(255, 255, 255, 0.06); border: 1px solid {status_color}; "
            f"border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 600; color: {status_color};"
        )
        top_row.addWidget(status_lbl)
        layout.addLayout(top_row)

        # Hardware & Details
        hw_lbl = QLabel(f"<b>Target Hardware / VID:</b> <code>{drv.target_hardware}</code>")
        hw_lbl.setProperty("cssClass", "muted")
        layout.addWidget(hw_lbl)

        desc_lbl = QLabel(drv.description)
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        # Action Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)

        if not drv.is_downloaded:
            btn_dl = QPushButton("Download Driver")
            btn_dl.setIcon(get_icon("downloads", 16))
            btn_dl.setMinimumHeight(32)
            btn_dl.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_dl.clicked.connect(lambda _, did=drv.id: self._on_download_driver(did))
            btn_row.addWidget(btn_dl)
        else:
            btn_inst = QPushButton("Install Driver (INF / Setup)")
            btn_inst.setIcon(get_icon("tools", 16))
            btn_inst.setProperty("cssClass", "primary")
            btn_inst.setMinimumHeight(32)
            btn_inst.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_inst.clicked.connect(lambda _, did=drv.id: self._on_install_driver(did))
            btn_row.addWidget(btn_inst)

        portal_url = drv.official_portal_url or drv.download_url
        if portal_url:
            btn_portal = QPushButton("Official Site")
            btn_portal.setIcon(get_icon("globe", 14))
            btn_portal.setMinimumHeight(32)
            btn_portal.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_portal.clicked.connect(lambda _, u=portal_url: QDesktopServices.openUrl(QUrl(u)))
            btn_row.addWidget(btn_portal)

        if drv.is_downloaded and drv.local_path:
            folder_p = drv.local_path if drv.local_path.is_dir() else drv.local_path.parent
            btn_folder = QPushButton("Folder")
            btn_folder.setIcon(get_icon("folder", 14))
            btn_folder.setMinimumHeight(32)
            btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_folder.clicked.connect(lambda _, f=folder_p: QDesktopServices.openUrl(QUrl.fromLocalFile(str(f))))
            btn_row.addWidget(btn_folder)

        layout.addLayout(btn_row)
        return card

    @Slot()
    def _on_scan_pnp_devices(self) -> None:
        """Scan Windows PnP device manager for driver errors."""
        self._status_label.setText("Scanning Windows PnP devices...")
        issues = self._driver_mgr.diagnose_pnp_devices()

        if not issues:
            QMessageBox.information(
                self,
                "Device Manager Scan",
                "No USB or Android driver issues detected.\n"
                "All connected devices are properly recognized by Windows.",
            )
            self._status_label.setText("PnP Scan: All connected devices OK.")
            return

        msg_lines = ["The following devices have driver warnings or errors in Windows:\n"]
        for item in issues:
            name = item.get("name", "Unknown")
            status = item.get("status", "Error")
            rec = item.get("recommended_driver", "")
            rec_line = f" -> Recommended: {rec}" if rec else ""
            msg_lines.append(f"• {name} (Status: {status}){rec_line}")

        msg_lines.append("\nTip: Download and install the recommended driver below.")
        QMessageBox.warning(self, "PnP Driver Issues Found", "\n".join(msg_lines))
        self._status_label.setText(f"Found {len(issues)} device(s) requiring drivers.")

    def _on_download_driver(self, driver_id: str) -> None:
        """Download an OEM driver package."""
        if self._active_worker and self._active_worker.is_alive():
            QMessageBox.information(self, "Busy", "A download operation is already running.")
            return

        def _worker():
            def _prog(cur, tot):
                self.progress_updated.emit(cur, tot)

            success, msg = self._driver_mgr.download_driver(driver_id, progress_callback=_prog)
            self.download_finished.emit(success, msg)

        self._active_worker = threading.Thread(target=_worker, daemon=True)
        self._active_worker.start()
        self._status_label.setText(f"Downloading driver '{driver_id}'...")

    def _on_install_driver(self, driver_id: str) -> None:
        """Install or launch driver setup."""
        success, msg = self._driver_mgr.install_driver(driver_id)
        if success:
            QMessageBox.information(self, "Driver Installation", msg)
        else:
            QMessageBox.warning(self, "Driver Installation", msg)
        self._refresh_drivers_table()

    @Slot()
    def _on_install_driver_from_file(self) -> None:
        """Let user pick any driver archive or executable from disk and install it."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Driver Package or Setup File",
            str(DRIVERS_DIR),
            "Driver Files (*.inf *.zip *.exe *.msi);;INF Driver Files (*.inf);;ZIP Archives (*.zip);;Executables (*.exe *.msi);;All Files (*.*)",
        )
        if not file_path:
            return

        p = Path(file_path)
        self._status_label.setText(f"Installing driver from {p.name}...")
        success, msg = self._driver_mgr.install_custom_driver_file(p)
        if success:
            QMessageBox.information(self, "Driver Installation", msg)
            self._status_label.setText(f"Driver installed: {p.name}")
        else:
            QMessageBox.warning(self, "Driver Installation Failed", msg)
            self._status_label.setText(f"Driver installation failed: {p.name}")
        self._refresh_drivers_table()

    # -------------------------------------------------------------------------
    # Logic: Firmware Repositories Tab
    # -------------------------------------------------------------------------

    def _set_fw_category(self, cat: str) -> None:
        self._active_fw_category = cat
        self._fw_cat_btn_all.setChecked(cat == "all")
        self._fw_cat_btn_factory.setChecked(cat == "factory")
        self._fw_cat_btn_gsi.setChecked(cat == "gsi")
        self._fw_cat_btn_rec.setChecked(cat == "recovery")
        self._populate_firmware_cards()

    def _filter_firmware_cards(self) -> None:
        self._populate_firmware_cards()

    def _populate_firmware_cards(self) -> None:
        """Re-render firmware repository cards matching category and search filter."""
        # Clear existing items
        while self._fw_cards_layout.count():
            item = self._fw_cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        search_query = self._fw_search_input.text().strip().lower()
        repos = self._firmware_finder.get_recommendations_for_device(self._current_device)

        # Filter by category
        if self._active_fw_category != "all":
            repos = [r for r in repos if r.category == self._active_fw_category]

        # Filter by search
        if search_query:
            repos = [
                r for r in repos
                if search_query in r.name.lower()
                or search_query in r.description.lower()
                or search_query in r.supported_models.lower()
                or search_query in r.brand.lower()
            ]

        if not repos:
            empty_lbl = QLabel("No repositories found matching current filter.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setProperty("cssClass", "muted")
            self._fw_cards_layout.addWidget(empty_lbl)
            return

        for repo in repos:
            card = self._make_repo_card(repo)
            self._fw_cards_layout.addWidget(card)

        self._fw_cards_layout.addStretch(1)

    def _make_repo_card(self, repo: FirmwareRepo) -> QFrame:
        card = QFrame()
        card.setProperty("cssClass", "card")
        box = QVBoxLayout(card)
        box.setSpacing(6)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        header_row.addWidget(create_icon_label("downloads", 16))
        title = QLabel(repo.name)
        title.setProperty("cssClass", "subheading")
        header_row.addWidget(title, 1)

        cat_badge = QLabel(f" {repo.category.upper()} ")
        cat_badge.setStyleSheet(
            "background-color: rgba(10, 132, 255, 0.15); color: #0A84FF; "
            "border-radius: 4px; font-size: 11px; font-weight: 600; padding: 2px 6px;"
        )
        header_row.addWidget(cat_badge)
        box.addLayout(header_row)

        desc = QLabel(repo.description)
        desc.setWordWrap(True)
        box.addWidget(desc)

        models = QLabel(f"<b>Supported Models:</b> {repo.supported_models}")
        models.setProperty("cssClass", "muted")
        box.addWidget(models)

        if repo.guide_note:
            note = QLabel(f"<b>Flashing Tip:</b> {repo.guide_note}")
            note.setStyleSheet("font-size: 11px; color: #FF9F0A;")
            box.addWidget(note)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        btn_open = QPushButton("Open Official Portal")
        btn_open.setIcon(get_icon("globe", 14))
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.setProperty("cssClass", "primary")
        btn_open.clicked.connect(lambda _, url=repo.url: QDesktopServices.openUrl(QUrl(url)))
        btn_row.addWidget(btn_open)

        box.addLayout(btn_row)
        return card

    # -------------------------------------------------------------------------
    # External API / Device Changes
    # -------------------------------------------------------------------------

    def load_for_device(self, device: Optional[DeviceInfo]) -> None:
        """Update indicators and recommendations when the connected device changes."""
        self._current_device = device
        if device and device.mode != "not_connected":
            brand = (device.brand or "").strip()
            model = (device.model or "").strip()
            codename = (device.device or "").strip()
            dev_text = f"{brand} {model} ({codename}) [{device.mode.upper()}]"
            self._device_badge.setText(dev_text)

            # Suggest driver
            rec_driver = "Google USB Driver"
            brand_lower = brand.lower()
            if "samsung" in brand_lower:
                rec_driver = "Samsung Mobile USB Driver"
            elif "xiaomi" in brand_lower or "redmi" in brand_lower or "poco" in brand_lower:
                rec_driver = "Xiaomi Fastboot Driver"
            elif "mediatek" in brand_lower or "mtk" in brand_lower:
                rec_driver = "MediaTek MTK VCOM Driver"

            self._driver_suggestion_lbl.setText(
                f"Connected: <b>{brand} {model}</b>. Recommended USB Driver: <b>{rec_driver}</b>."
            )
        else:
            self._device_badge.setText("No device connected")
            self._driver_suggestion_lbl.setText(
                "Plug in your device to get targeted driver recommendations."
            )

        self._populate_firmware_cards()
