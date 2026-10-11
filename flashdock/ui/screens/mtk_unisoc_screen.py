"""
FlashDock — MediaTek (MTK) & Unisoc (SPD) Flasher Screen.

Provides interactive GUI for:
1. MediaTek BROM connection, SLA/DAA auth bypass, scatter file loading, and partition flashing.
2. Unisoc / Spreadtrum PAC firmware parsing, FDL1/FDL2 two-stage execution, and partition flashing.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from flashdock.core.device import DeviceInfo
from flashdock.core.mtk import (
    AuthBypassHandler,
    MTKBROMManager,
    MTKFlashPipeline,
    ScatterInfo,
    ScatterParser,
)
from flashdock.core.unisoc import (
    PACExtractor,
    PACInfo,
    UnisocFlashPipeline,
)
from flashdock.logger import get_logger

log = get_logger("ui.mtk_unisoc")


class MtkUnisocScreen(QWidget):
    """MediaTek BROM and Unisoc PAC Flashing GUI screen."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._brom_mgr = MTKBROMManager()
        self._auth_handler = AuthBypassHandler(self._brom_mgr)
        self._mtk_pipeline = MTKFlashPipeline(self._brom_mgr, self._auth_handler)
        self._current_scatter: Optional[ScatterInfo] = None
        self._scatter_dir: Optional[Path] = None

        self._unisoc_pipeline = UnisocFlashPipeline()
        self._current_pac: Optional[PACInfo] = None
        self._pac_path: Optional[Path] = None

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 16, 24, 16)
        main_layout.setSpacing(14)

        # Tabs: Tab 1 = MediaTek BROM, Tab 2 = Unisoc PAC
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_mtk_tab(), "⚙️ MediaTek (BROM / Scatter)")
        self._tabs.addTab(self._build_unisoc_tab(), "⚡ Unisoc (SPD / PAC)")
        main_layout.addWidget(self._tabs)

    # ==================================================================
    # Tab 1: MediaTek BROM & Scatter
    # ==================================================================

    def _build_mtk_tab(self) -> QWidget:
        widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Header
        head_box = QVBoxLayout()
        title = QLabel("⚙️ MediaTek BROM & Scatter Flasher")
        title.setProperty("cssClass", "heading")
        sub = QLabel("Direct BootROM hardware connection, SLA/DAA auth bypass, and scatter partition flashing.")
        sub.setProperty("cssClass", "muted")
        head_box.addWidget(title)
        head_box.addWidget(sub)
        layout.addLayout(head_box)

        # BROM Connection & Auth Card
        conn_group = QGroupBox("BROM Hardware Link & Auth Status")
        conn_layout = QVBoxLayout(conn_group)
        conn_layout.setSpacing(10)

        status_row = QHBoxLayout()
        self._mtk_status_lbl = QLabel("🔴 Disconnected (Hold Vol+ & Vol- while plugging in USB cable)")
        self._mtk_status_lbl.setProperty("cssClass", "muted")
        status_row.addWidget(self._mtk_status_lbl, 1)

        self._mtk_auth_lbl = QLabel("Auth: Locked")
        self._mtk_auth_lbl.setProperty("cssClass", "muted")
        status_row.addWidget(self._mtk_auth_lbl)
        conn_layout.addLayout(status_row)

        btn_row = QHBoxLayout()
        self._btn_mtk_connect = QPushButton("⚡ Connect BROM Handshake")
        self._btn_mtk_connect.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_mtk_connect.clicked.connect(self._on_mtk_connect)
        btn_row.addWidget(self._btn_mtk_connect)

        self._btn_mtk_bypass = QPushButton("🔓 SLA / DAA Auth Bypass")
        self._btn_mtk_bypass.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_mtk_bypass.setEnabled(False)
        self._btn_mtk_bypass.clicked.connect(self._on_mtk_bypass)
        btn_row.addWidget(self._btn_mtk_bypass)

        self._btn_mtk_reboot = QPushButton("🔄 Reboot Phone")
        self._btn_mtk_reboot.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_mtk_reboot.setEnabled(False)
        self._btn_mtk_reboot.clicked.connect(self._on_mtk_reboot)
        btn_row.addWidget(self._btn_mtk_reboot)

        conn_layout.addLayout(btn_row)
        layout.addWidget(conn_group)

        # Scatter File Picker Card
        scatter_group = QGroupBox("Scatter File & Partition Map")
        scatter_layout = QVBoxLayout(scatter_group)
        scatter_layout.setSpacing(10)

        picker_row = QHBoxLayout()
        self._scatter_path_edit = QLineEdit()
        self._scatter_path_edit.setPlaceholderText("Select MT67xx / MT68xx Android scatter text file...")
        self._scatter_path_edit.setReadOnly(True)
        picker_row.addWidget(self._scatter_path_edit, 1)

        btn_browse_scatter = QPushButton("Browse Scatter...")
        btn_browse_scatter.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse_scatter.clicked.connect(self._on_browse_scatter)
        picker_row.addWidget(btn_browse_scatter)
        scatter_layout.addLayout(picker_row)

        self._scatter_info_lbl = QLabel("No scatter file loaded.")
        self._scatter_info_lbl.setProperty("cssClass", "muted")
        scatter_layout.addWidget(self._scatter_info_lbl)

        # Scatter Table
        self._scatter_table = QTableWidget()
        self._scatter_table.setColumnCount(5)
        self._scatter_table.setHorizontalHeaderLabels([
            "Flash", "Partition Name", "Image File", "Start Address", "Size (Bytes)"
        ])
        self._scatter_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._scatter_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._scatter_table.setMinimumHeight(240)
        scatter_layout.addWidget(self._scatter_table)

        # Safety & Flash Button
        action_row = QHBoxLayout()
        self._chk_protect_preloader = QCheckBox("🛡️ Protect Preloader (Safety Guard: prevent bricking)")
        self._chk_protect_preloader.setChecked(True)
        action_row.addWidget(self._chk_protect_preloader, 1)

        self._btn_mtk_flash = QPushButton("⚡ Flash Partitions via BROM")
        self._btn_mtk_flash.setProperty("cssClass", "primary")
        self._btn_mtk_flash.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_mtk_flash.setEnabled(False)
        self._btn_mtk_flash.clicked.connect(self._on_mtk_flash)
        action_row.addWidget(self._btn_mtk_flash)
        scatter_layout.addLayout(action_row)

        self._mtk_progress = QProgressBar()
        self._mtk_progress.setVisible(False)
        scatter_layout.addWidget(self._mtk_progress)

        layout.addWidget(scatter_group)
        layout.addStretch(1)

        scroll.setWidget(container)
        widget_layout = QVBoxLayout(widget)
        widget_layout.setContentsMargins(0, 0, 0, 0)
        widget_layout.addWidget(scroll)
        return widget

    # ==================================================================
    # Tab 2: Unisoc PAC & FDL
    # ==================================================================

    def _build_unisoc_tab(self) -> QWidget:
        widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Header
        head_box = QVBoxLayout()
        title = QLabel("⚡ Unisoc / Spreadtrum PAC Flasher")
        title.setProperty("cssClass", "heading")
        sub = QLabel("Unisoc Bootloader Serial Link (BSL), two-stage FDL1/FDL2 loading, and PAC flashing.")
        sub.setProperty("cssClass", "muted")
        head_box.addWidget(title)
        head_box.addWidget(sub)
        layout.addLayout(head_box)

        # Connection Card
        conn_group = QGroupBox("Unisoc BSL Connection")
        conn_layout = QVBoxLayout(conn_group)
        conn_layout.setSpacing(10)

        conn_row = QHBoxLayout()
        self._unisoc_status_lbl = QLabel("🔴 Disconnected (Hold Vol- while connecting USB cable)")
        self._unisoc_status_lbl.setProperty("cssClass", "muted")
        conn_row.addWidget(self._unisoc_status_lbl, 1)

        self._btn_unisoc_connect = QPushButton("⚡ BSL Handshake")
        self._btn_unisoc_connect.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_unisoc_connect.clicked.connect(self._on_unisoc_connect)
        conn_row.addWidget(self._btn_unisoc_connect)
        conn_layout.addLayout(conn_row)
        layout.addWidget(conn_group)

        # PAC Archive Card
        pac_group = QGroupBox("PAC Firmware Archive (.pac)")
        pac_layout = QVBoxLayout(pac_group)
        pac_layout.setSpacing(10)

        picker_row = QHBoxLayout()
        self._pac_path_edit = QLineEdit()
        self._pac_path_edit.setPlaceholderText("Select Unisoc / Spreadtrum .pac firmware archive...")
        self._pac_path_edit.setReadOnly(True)
        picker_row.addWidget(self._pac_path_edit, 1)

        btn_browse_pac = QPushButton("Browse PAC...")
        btn_browse_pac.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse_pac.clicked.connect(self._on_browse_pac)
        picker_row.addWidget(btn_browse_pac)
        pac_layout.addLayout(picker_row)

        self._pac_info_lbl = QLabel("No PAC file loaded.")
        self._pac_info_lbl.setProperty("cssClass", "muted")
        pac_layout.addWidget(self._pac_info_lbl)

        # PAC Table
        self._pac_table = QTableWidget()
        self._pac_table.setColumnCount(4)
        self._pac_table.setHorizontalHeaderLabels([
            "File ID", "File Name", "Size (Bytes)", "Offset in PAC"
        ])
        self._pac_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._pac_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._pac_table.setMinimumHeight(240)
        pac_layout.addWidget(self._pac_table)

        # Action Buttons
        act_row = QHBoxLayout()
        self._btn_pac_extract = QPushButton("📦 Extract All PAC Images")
        self._btn_pac_extract.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_pac_extract.setEnabled(False)
        self._btn_pac_extract.clicked.connect(self._on_extract_pac)
        act_row.addWidget(self._btn_pac_extract)

        self._btn_pac_flash = QPushButton("⚡ Flash Full PAC Firmware")
        self._btn_pac_flash.setProperty("cssClass", "primary")
        self._btn_pac_flash.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_pac_flash.setEnabled(False)
        self._btn_pac_flash.clicked.connect(self._on_flash_pac)
        act_row.addWidget(self._btn_pac_flash)
        pac_layout.addLayout(act_row)

        self._unisoc_progress = QProgressBar()
        self._unisoc_progress.setVisible(False)
        pac_layout.addWidget(self._unisoc_progress)

        layout.addWidget(pac_group)
        layout.addStretch(1)

        scroll.setWidget(container)
        widget_layout = QVBoxLayout(widget)
        widget_layout.setContentsMargins(0, 0, 0, 0)
        widget_layout.addWidget(scroll)
        return widget

    # ==================================================================
    # Handlers: MediaTek
    # ==================================================================

    def _on_mtk_connect(self) -> None:
        if self._brom_mgr.connect():
            self._mtk_status_lbl.setText(
                f"🟢 Connected: {self._brom_mgr.hw_name} (HW: 0x{self._brom_mgr.hw_code:04X})"
            )
            self._btn_mtk_bypass.setEnabled(True)
            self._btn_mtk_reboot.setEnabled(True)
            self._update_mtk_flash_state()
            QMessageBox.information(
                self,
                "BROM Handshake",
                f"Successfully connected to MediaTek BROM!\n\n"
                f"Chipset: {self._brom_mgr.hw_name}\n"
                f"Hardware Code: 0x{self._brom_mgr.hw_code:04X}",
            )
        else:
            QMessageBox.warning(
                self,
                "MTK Backend Unavailable",
                "This build does not include a physical MediaTek BROM USB backend, so no simulated "
                "connection or flash will be performed.\n\nUse Fastboot/ADB tools, or install a supported "
                "vendor backend before attempting low-level recovery.",
            )

    def _on_mtk_bypass(self) -> None:
        if self._auth_handler.bypass_sla_daa():
            self._mtk_auth_lbl.setText("Auth: 🟢 Bypassed (Watchdog Disabled)")
            self._btn_mtk_bypass.setEnabled(False)
            self._update_mtk_flash_state()
            QMessageBox.information(
                self,
                "Auth Bypass",
                "SLA & DAA Auth Bypass successfully executed!\n\n"
                "Watchdog timer has been disabled. You can now download partitions without OEM service tokens.",
            )
        else:
            QMessageBox.warning(self, "Bypass Failed", "Failed to disable SLA / DAA auth.")

    def _on_mtk_reboot(self) -> None:
        if self._brom_mgr.reboot():
            self._mtk_status_lbl.setText("🔴 Disconnected (Rebooted)")
            self._btn_mtk_bypass.setEnabled(False)
            self._btn_mtk_reboot.setEnabled(False)
            self._btn_mtk_flash.setEnabled(False)
            QMessageBox.information(self, "Device Reboot", "Reboot signal sent successfully.")
        else:
            QMessageBox.warning(self, "Reboot Failed", "Failed to send reboot command.")

    def _on_browse_scatter(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select MediaTek Scatter File",
            "",
            "Scatter Files (*.txt);;All Files (*.*)",
        )
        if not file_path:
            return

        try:
            scatter = ScatterParser.parse_file(file_path)
            self._current_scatter = scatter
            self._scatter_dir = Path(file_path).parent
            self._scatter_path_edit.setText(file_path)

            self._scatter_info_lbl.setText(
                f"Platform: {scatter.platform}  |  Storage: {scatter.storage_type}  |  "
                f"Partitions: {len(scatter.partitions)} ({len(scatter.download_partitions)} downloadable)"
            )

            # Populate table
            self._scatter_table.setRowCount(len(scatter.partitions))
            for row, p in enumerate(scatter.partitions):
                # Checkbox
                chk = QTableWidgetItem()
                chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                chk.setCheckState(Qt.CheckState.Checked if p.is_download and not p.is_empty else Qt.CheckState.Unchecked)
                self._scatter_table.setItem(row, 0, chk)

                self._scatter_table.setItem(row, 1, QTableWidgetItem(p.partition_name))
                self._scatter_table.setItem(row, 2, QTableWidgetItem(p.file_name))
                self._scatter_table.setItem(row, 3, QTableWidgetItem(f"0x{p.linear_start_addr:08X}"))
                self._scatter_table.setItem(row, 4, QTableWidgetItem(f"{p.partition_size:,}"))

            self._update_mtk_flash_state()

        except Exception as e:
            QMessageBox.critical(self, "Error Reading Scatter", f"Failed to parse scatter file:\n\n{e}")

    def _update_mtk_flash_state(self) -> None:
        can_flash = bool(self._brom_mgr.connected and self._current_scatter and self._scatter_dir)
        self._btn_mtk_flash.setEnabled(can_flash)

    def _on_mtk_flash(self) -> None:
        if not self._current_scatter or not self._scatter_dir:
            return

        protect_preloader = self._chk_protect_preloader.isChecked()
        reply = QMessageBox.question(
            self,
            "Confirm Flash",
            f"Are you sure you want to flash the firmware for {self._current_scatter.platform}?\n\n"
            f"Protect Preloader: {'YES (Safe)' if protect_preloader else 'NO (High Risk)'}\n\n"
            "Do not disconnect the USB cable during this process.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._mtk_progress.setVisible(True)
        self._mtk_progress.setValue(0)

        def _prog_cb(part: str, pct: int, size: int) -> None:
            self._mtk_progress.setValue(pct)

        self._mtk_pipeline.progress_callback = _prog_cb
        success = self._mtk_pipeline.execute_flash(
            self._current_scatter, self._scatter_dir, allow_preloader=not protect_preloader
        )
        self._mtk_progress.setVisible(False)

        if success:
            QMessageBox.information(self, "Flashing Complete", "All selected partitions flashed successfully!")
        else:
            QMessageBox.critical(self, "Flashing Failed", "An error occurred while downloading partitions.")

    # ==================================================================
    # Handlers: Unisoc
    # ==================================================================

    def _on_unisoc_connect(self) -> None:
        if self._unisoc_pipeline.connect():
            self._unisoc_status_lbl.setText("🟢 Connected in SPRD U2S Diag / Download Mode")
            self._btn_unisoc_connect.setEnabled(False)
            self._update_unisoc_state()
            QMessageBox.information(
                self,
                "Unisoc BSL Connect",
                "Connected to Unisoc Bootloader Serial Link (BSL)!\nReady for FDL handshake.",
            )
        else:
            QMessageBox.warning(
                self,
                "Unisoc Backend Unavailable",
                "This build does not include a physical Unisoc BSL USB backend, so no simulated "
                "connection or flash will be performed.\n\nUse Fastboot/ADB tools, or install a supported "
                "vendor backend before attempting low-level recovery.",
            )

    def _on_browse_pac(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Unisoc PAC Firmware File",
            "",
            "PAC Firmware Files (*.pac);;All Files (*.*)",
        )
        if not file_path:
            return

        try:
            info = PACExtractor.parse_pac(file_path)
            self._current_pac = info
            self._pac_path = Path(file_path)
            self._pac_path_edit.setText(file_path)

            self._pac_info_lbl.setText(
                f"Product: {info.product_name}  |  Version: {info.product_version}  |  "
                f"Files: {len(info.files)}"
            )

            # Populate table
            self._pac_table.setRowCount(len(info.files))
            for row, f in enumerate(info.files):
                self._pac_table.setItem(row, 0, QTableWidgetItem(f.file_id))
                self._pac_table.setItem(row, 1, QTableWidgetItem(f.file_name))
                self._pac_table.setItem(row, 2, QTableWidgetItem(f"{f.file_size:,}"))
                self._pac_table.setItem(row, 3, QTableWidgetItem(f"0x{f.data_offset:08X}"))

            self._btn_pac_extract.setEnabled(True)
            self._update_unisoc_state()

        except Exception as e:
            QMessageBox.critical(self, "Error Reading PAC", f"Failed to parse PAC firmware:\n\n{e}")

    def _update_unisoc_state(self) -> None:
        can_flash = bool(self._unisoc_pipeline.connected and self._current_pac and self._pac_path)
        self._btn_pac_flash.setEnabled(can_flash)

    def _on_extract_pac(self) -> None:
        if not self._pac_path:
            return

        dest_dir = QFileDialog.getExistingDirectory(self, "Select Extraction Directory")
        if not dest_dir:
            return

        self._unisoc_progress.setVisible(True)
        self._unisoc_progress.setValue(0)

        def _prog(file_id: str, pct: int) -> None:
            self._unisoc_progress.setValue(pct)

        try:
            files = PACExtractor.extract_all(self._pac_path, dest_dir, progress_cb=_prog)
            self._unisoc_progress.setVisible(False)
            QMessageBox.information(
                self,
                "Extraction Finished",
                f"Successfully extracted {len(files)} partition images to:\n\n{dest_dir}",
            )
        except Exception as e:
            self._unisoc_progress.setVisible(False)
            QMessageBox.critical(self, "Extraction Error", f"Failed to extract PAC archive:\n\n{e}")

    def _on_flash_pac(self) -> None:
        if not self._pac_path or not self._current_pac:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Full PAC Flash",
            f"Are you sure you want to flash the firmware for {self._current_pac.product_name}?\n\n"
            "This will execute the two-stage FDL1 -> SRAM and FDL2 -> DRAM loaders, then wipe and flash all partitions.\n\n"
            "Do not disconnect the USB cable during this operation.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._unisoc_progress.setVisible(True)
        self._unisoc_progress.setValue(0)

        def _prog(file_id: str, pct: int) -> None:
            self._unisoc_progress.setValue(pct)

        extract_dir = self._pac_path.parent / "_pac_unpacked"
        success = self._unisoc_pipeline.flash_pac(
            self._pac_path, extract_dir, progress_cb=_prog
        )
        self._unisoc_progress.setVisible(False)

        if success:
            QMessageBox.information(self, "Flashing Complete", "Unisoc PAC firmware flashed successfully!")
        else:
            QMessageBox.critical(self, "Flashing Failed", "An error occurred during Unisoc PAC flashing.")

    # ==================================================================
    # Public interface
    # ==================================================================

    def load_for_device(self, info: Optional[DeviceInfo]) -> None:
        """Automatically selects MTK or Unisoc tab based on detected chipset family."""
        if not info:
            return

        chipset = (info.chipset or "").lower()
        hw = (info.hardware or "").lower()

        if any(k in chipset or k in hw for k in ("mt", "mediatek", "helio", "dimensity")):
            self._tabs.setCurrentIndex(0)
        elif any(k in chipset or k in hw for k in ("unisoc", "spreadtrum", "spd", "sc98", "ums")):
            self._tabs.setCurrentIndex(1)
