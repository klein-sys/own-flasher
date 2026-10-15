"""
FlashDock — Backup & Restore Screen.

GUI for:
* One-click critical partition dumps (boot, recovery, vbmeta, EFS).
* Full ADB application and storage backups (.ab).
* Catalog of existing backups with checksum indicators.
* Safe partition restoration via fastboot with typed confirmation.

Spec references: Section 10.8, Section 16.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from flashdock.constants import CONFIRMATION_WORD
from flashdock.core.backup import BackupInfo, BackupManager
from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.core.safety import SafetyEngine
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot
from flashdock.ui.icon_assets import create_icon_label, get_icon
from flashdock.ui.widgets.flash_shield import FlashShieldDialog

log = get_logger(__name__)

# Common partitions users might want to back up
RECOMMENDED_PARTITIONS = ["boot", "recovery", "vbmeta", "init_boot", "vendor_boot"]
CRITICAL_RADIO_PARTITIONS = ["efs", "nvram", "nvdata", "modem", "persist"]


class BackupWorker(QThread):
    progress_changed = Signal(str, int)  # message, percent
    finished = Signal(bool, str)

    def __init__(
        self,
        backup_mgr: BackupManager,
        action: str,
        device: DeviceInfo,
        adb: ADB,
        fastboot: Fastboot,
        partitions: Optional[list[str]] = None,
        include_apk: bool = False,
        include_shared: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.backup_mgr = backup_mgr
        self.action = action
        self.device = device
        self.adb = adb
        self.fastboot = fastboot
        self.partitions = partitions or []
        self.include_apk = include_apk
        self.include_shared = include_shared

    def run(self) -> None:
        try:
            if self.action == "partition":
                def cb(part: str, idx: int, total: int):
                    pct = int((idx / total) * 90) if total > 0 else 0
                    self.progress_changed.emit(f"Dumping '{part}' partition ({idx}/{total})...", pct)

                info = self.backup_mgr.create_partition_backup(
                    device=self.device,
                    partitions=self.partitions,
                    adb=self.adb,
                    fastboot=self.fastboot,
                    dry_run=False,
                    on_progress=cb,
                )
                self.finished.emit(True, f"Partition backup saved ({len(info.items)} partitions).")
            elif self.action == "adb":
                info = self.backup_mgr.create_adb_backup(
                    device=self.device,
                    adb=self.adb,
                    include_apk=self.include_apk,
                    include_shared=self.include_shared,
                    dry_run=False,
                )
                self.finished.emit(True, f"ADB backup complete: {info.backup_id}")
        except Exception as e:
            self.finished.emit(False, str(e))


class BackupScreen(QWidget):
    """The Backup & Restore management screen."""

    def __init__(
        self,
        device_mgr: DeviceManager,
        adb: ADB,
        fastboot: Fastboot,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._device_mgr = device_mgr
        self._adb = adb
        self._fb = fastboot
        self._backup_mgr = BackupManager()
        self._current_device: Optional[DeviceInfo] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        # Header
        title_h = QHBoxLayout()
        title_h.setSpacing(8)
        title_h.addWidget(create_icon_label("backup", 22))
        title = QLabel("Backup & Restore Manager")
        title.setProperty("cssClass", "heading")
        title_h.addWidget(title)
        title_h.addStretch(1)
        layout.addLayout(title_h)

        self._subtitle = QLabel("Protect your device data and critical firmware partitions before flashing.")
        self._subtitle.setProperty("cssClass", "muted")
        layout.addWidget(self._subtitle)

        # Tabs
        self._tabs = QTabWidget()

        self._tab_partitions = QWidget()
        self._tab_adb = QWidget()
        self._tab_restore = QWidget()

        self._setup_partitions_tab()
        self._setup_adb_tab()
        self._setup_restore_tab()

        self._tabs.addTab(self._tab_partitions, get_icon("backup", 16), "Partition Backup")
        self._tabs.addTab(self._tab_adb, get_icon("phone", 16), "Full ADB Backup")
        self._tabs.addTab(self._tab_restore, get_icon("refresh", 16), "Restore Backups")

        layout.addWidget(self._tabs, 1)

    # -----------------------------------------------------------------------
    # Tab 1: Partition Backup
    # -----------------------------------------------------------------------

    def _setup_partitions_tab(self) -> None:
        layout = QVBoxLayout(self._tab_partitions)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        info = QLabel(
            "Dump raw partition images directly from your phone. Having your stock boot, recovery, "
            "and vbmeta allows you to safely recover or patch images without re-downloading full firmware."
        )
        info.setWordWrap(True)
        info.setProperty("cssClass", "muted")
        layout.addWidget(info)

        # Radio/EFS warning
        efs_frame = QFrame()
        efs_frame.setProperty("cssClass", "info_banner")
        ef_layout = QHBoxLayout(efs_frame)
        ef_layout.setContentsMargins(10, 6, 10, 6)
        ef_layout.setSpacing(8)
        ef_layout.addWidget(create_icon_label("info", 16))
        efs_warn = QLabel("TIP: Backing up EFS / NVRAM partitions preserves your device's unique IMEI and radio calibration data.")
        efs_warn.setWordWrap(True)
        ef_layout.addWidget(efs_warn, 1)
        layout.addWidget(efs_frame)

        # Checkboxes for partitions (2 clean columns: Standard vs Radio/Critical)
        part_group = QFrame()
        part_group.setProperty("cssClass", "card")
        part_group.setStyleSheet(
            "QFrame[cssClass='card'] { background-color: rgba(255, 255, 255, 0.04); "
            "border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 14px; }"
        )
        part_grid = QGridLayout(part_group)
        part_grid.setContentsMargins(14, 12, 14, 12)
        part_grid.setHorizontalSpacing(24)
        part_grid.setVerticalSpacing(8)

        # Header labels for columns
        lbl_col1 = QLabel("STANDARD FIRMWARE PARTITIONS")
        lbl_col1.setStyleSheet("font-size: 11px; font-weight: 700; color: #8E8E93; letter-spacing: 0.5px;")
        part_grid.addWidget(lbl_col1, 0, 0)

        lbl_col2 = QLabel("RADIO & CALIBRATION (NV/EFS)")
        lbl_col2.setStyleSheet("font-size: 11px; font-weight: 700; color: #FF9F0A; letter-spacing: 0.5px;")
        part_grid.addWidget(lbl_col2, 0, 1)

        self._part_checkboxes: dict[str, QCheckBox] = {}
        cb_style = (
            "QCheckBox { min-height: 28px; padding: 4px 8px; margin: 2px; font-size: 12px; font-weight: 600; color: #E6EDF3; } "
            "QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; } "
            "QCheckBox:hover { background-color: rgba(255, 255, 255, 0.04); border-radius: 6px; }"
        )

        for row_idx, p in enumerate(RECOMMENDED_PARTITIONS, start=1):
            cb = QCheckBox(f"{p} partition")
            cb.setStyleSheet(cb_style)
            if p in ("boot", "recovery", "vbmeta"):
                cb.setChecked(True)
            self._part_checkboxes[p] = cb
            part_grid.addWidget(cb, row_idx, 0)

        for row_idx, p in enumerate(CRITICAL_RADIO_PARTITIONS, start=1):
            cb = QCheckBox(f"{p} partition")
            cb.setStyleSheet(cb_style)
            self._part_checkboxes[p] = cb
            part_grid.addWidget(cb, row_idx, 1)

        layout.addWidget(part_group)

        # Actions row
        btn_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.setProperty("cssClass", "secondary")
        select_all_btn.clicked.connect(lambda: [cb.setChecked(True) for cb in self._part_checkboxes.values()])
        btn_row.addWidget(select_all_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setProperty("cssClass", "secondary")
        clear_btn.clicked.connect(lambda: [cb.setChecked(False) for cb in self._part_checkboxes.values()])
        btn_row.addWidget(clear_btn)

        btn_row.addStretch()

        self._btn_start_part_backup = QPushButton("Start Partition Backup")
        self._btn_start_part_backup.setIcon(get_icon("play", 14))
        self._btn_start_part_backup.setProperty("cssClass", "primary")
        self._btn_start_part_backup.clicked.connect(self._on_start_partition_backup)
        btn_row.addWidget(self._btn_start_part_backup)

        layout.addLayout(btn_row)
        layout.addStretch()

    # -----------------------------------------------------------------------
    # Tab 2: ADB Full Backup
    # -----------------------------------------------------------------------

    def _setup_adb_tab(self) -> None:
        layout = QVBoxLayout(self._tab_adb)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        info = QLabel(
            "Creates an Android backup archive (.ab) over ADB containing your installed applications and personal app data.\n"
            "This works without root access."
        )
        info.setWordWrap(True)
        info.setProperty("cssClass", "muted")
        layout.addWidget(info)

        self._cb_adb_apk = QCheckBox("Include application APK files in the backup")
        layout.addWidget(self._cb_adb_apk)

        self._cb_adb_shared = QCheckBox("Include shared internal storage (/sdcard)")
        layout.addWidget(self._cb_adb_shared)

        note_frame = QFrame()
        note_frame.setProperty("cssClass", "warn_banner")
        nf_layout = QHBoxLayout(note_frame)
        nf_layout.setContentsMargins(10, 6, 10, 6)
        nf_layout.setSpacing(8)
        nf_layout.addWidget(create_icon_label("warning", 16))
        note_box = QLabel(
            "ON-PHONE ACTION REQUIRED:\n"
            "After clicking 'Start ADB Backup', unlock your phone screen and tap 'Back up my data' when prompted."
        )
        note_box.setWordWrap(True)
        nf_layout.addWidget(note_box, 1)
        layout.addWidget(note_frame)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._btn_start_adb_backup = QPushButton("Start ADB Backup")
        self._btn_start_adb_backup.setIcon(get_icon("play", 14))
        self._btn_start_adb_backup.setProperty("cssClass", "primary")
        self._btn_start_adb_backup.clicked.connect(self._on_start_adb_backup)
        btn_row.addWidget(self._btn_start_adb_backup)

        layout.addLayout(btn_row)

    # -----------------------------------------------------------------------
    # Tab 3: Restore Tab
    # -----------------------------------------------------------------------

    def _setup_restore_tab(self) -> None:
        layout = QVBoxLayout(self._tab_restore)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        info = QLabel("Stored Backups Catalog")
        info.setProperty("cssClass", "subheading")
        header_row.addWidget(info)
        header_row.addStretch()

        refresh_btn = QPushButton("Refresh Catalog")
        refresh_btn.setIcon(get_icon("refresh", 14))
        refresh_btn.setProperty("cssClass", "secondary")
        refresh_btn.clicked.connect(self.refresh_catalog)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        # Backups Table
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Backup ID", "Device", "Type", "Contents", "Date"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self._table, 1)

        # Action row
        btn_row = QHBoxLayout()

        self._btn_delete_backup = QPushButton("Delete Backup")
        self._btn_delete_backup.setIcon(get_icon("trash", 14))
        self._btn_delete_backup.setProperty("cssClass", "danger")
        self._btn_delete_backup.clicked.connect(self._on_delete_backup)
        btn_row.addWidget(self._btn_delete_backup)

        btn_row.addStretch()

        self._btn_restore = QPushButton("Restore Partition...")
        self._btn_restore.setIcon(get_icon("flash", 14))
        self._btn_restore.setProperty("cssClass", "primary")
        self._btn_restore.clicked.connect(self._on_restore_selected)
        btn_row.addWidget(self._btn_restore)

        layout.addLayout(btn_row)

    # -----------------------------------------------------------------------
    # Device loading & catalog
    # -----------------------------------------------------------------------

    def load_for_device(self, device: Optional[DeviceInfo]) -> None:
        """Update screen context when device changes."""
        self._current_device = device
        if device and device.mode != "not_connected":
            self._subtitle.setText(f"Active Device: {device.summary_line} ({device.serial})")
        else:
            self._subtitle.setText("No device connected. Connect via USB to perform backups or restores.")
        self.refresh_catalog()

    def refresh_catalog(self) -> None:
        """Scan backups on disk and update table."""
        serial = self._current_device.serial if self._current_device else ""
        backups = self._backup_mgr.list_backups(serial=serial)

        self._table.setRowCount(len(backups))
        self._cached_backups = backups

        for row, b in enumerate(backups):
            self._table.setItem(row, 0, QTableWidgetItem(b.backup_id))
            self._table.setItem(row, 1, QTableWidgetItem(f"{b.brand} {b.model}"))
            self._table.setItem(row, 2, QTableWidgetItem(b.backup_type))
            items_str = ", ".join(it.name for it in b.items[:4])
            if len(b.items) > 4:
                items_str += f" (+{len(b.items) - 4} more)"
            self._table.setItem(row, 3, QTableWidgetItem(items_str or "none"))
            self._table.setItem(row, 4, QTableWidgetItem(b.created_at[:19].replace("T", " ")))

    # -----------------------------------------------------------------------
    # Backup operations
    # -----------------------------------------------------------------------

    def _on_start_partition_backup(self) -> None:
        device = self._current_device
        if not device or device.mode == "not_connected":
            QMessageBox.warning(self, "No Device", "Please connect a device first.")
            return

        selected = [p for p, cb in self._part_checkboxes.items() if cb.isChecked()]
        if not selected:
            QMessageBox.information(self, "No Partitions", "Please select at least one partition to back up.")
            return

        # Check battery
        battery_res = SafetyEngine.check_battery(device.battery_level)
        if battery_res.is_blocked:
            QMessageBox.warning(self, "Battery Low", battery_res.message)
            return

        # Start backup
        shield = FlashShieldDialog(self)
        shield.show()
        shield.update_progress("Starting partition backup...", 10)

        self._backup_worker = BackupWorker(
            backup_mgr=self._backup_mgr,
            action="partition",
            device=device,
            adb=self._adb,
            fastboot=self._fb,
            partitions=selected,
            parent=self,
        )
        self._backup_worker.progress_changed.connect(shield.update_progress)

        def _on_part_done(ok: bool, msg: str) -> None:
            shield.mark_completed(ok, msg)
            if ok:
                self.refresh_catalog()

        self._backup_worker.finished.connect(_on_part_done)
        self._backup_worker.start()

    def _on_start_adb_backup(self) -> None:
        device = self._current_device
        if not device or device.mode == "not_connected":
            QMessageBox.warning(self, "No Device", "Please connect a device first.")
            return

        include_apk = self._cb_adb_apk.isChecked()
        include_shared = self._cb_adb_shared.isChecked()

        shield = FlashShieldDialog(self)
        shield.show()
        shield.update_progress("Initiating ADB backup. Confirm on your phone screen...", 20)

        self._backup_worker = BackupWorker(
            backup_mgr=self._backup_mgr,
            action="adb",
            device=device,
            adb=self._adb,
            fastboot=self._fb,
            include_apk=include_apk,
            include_shared=include_shared,
            parent=self,
        )

        def _on_adb_done(ok: bool, msg: str) -> None:
            shield.mark_completed(ok, msg)
            if ok:
                self.refresh_catalog()

        self._backup_worker.finished.connect(_on_adb_done)
        self._backup_worker.start()

    # -----------------------------------------------------------------------
    # Restore operations
    # -----------------------------------------------------------------------

    def _on_delete_backup(self) -> None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "Select Backup", "Please select a backup row to delete.")
            return

        row = selected_rows[0].row()
        b_info = self._cached_backups[row]

        reply = QMessageBox.question(
            self,
            "Delete Backup?",
            f"Are you sure you want to permanently delete backup '{b_info.backup_id}'?\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._backup_mgr.delete_backup(b_info.backup_id, serial=b_info.serial)
            self.refresh_catalog()

    def _on_restore_selected(self) -> None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "Select Backup", "Please select a backup row from the table.")
            return

        row = selected_rows[0].row()
        b_info = self._cached_backups[row]

        if b_info.backup_type != "partitions" or not b_info.items:
            QMessageBox.information(
                self,
                "Cannot Restore Directly",
                "Full ADB backups (.ab) can be restored using the standard 'adb restore' command.",
            )
            return

        # Choose partition to restore
        part_names = [it.name for it in b_info.items if it.name]
        part, ok = QInputDialog.getItem(
            self,
            "Select Partition to Restore",
            f"Choose which partition from backup '{b_info.backup_id}' to flash:",
            part_names,
            0,
            False,
        )
        if not ok or not part:
            return

        # Typed confirmation guard (Section 16 requirement)
        confirm_word = SafetyEngine.expected_confirmation_word()
        text, ok = QInputDialog.getText(
            self,
            f"Confirm Flashing {part.upper()}",
            f"RESTORE WARNING:\n\n"
            f"This will OVERWRITE the '{part}' partition on your phone with the backed-up image.\n\n"
            f"Type '{confirm_word}' to proceed:",
        )
        if not ok or text.strip() != confirm_word:
            QMessageBox.information(self, "Cancelled", "Confirmation word was not entered. Restore cancelled.")
            return

        # Open Flash Shield modal guard during restore
        shield = FlashShieldDialog(self)
        shield.show()
        shield.update_progress(f"Restoring '{part}' partition via fastboot...", 50)

        success, msg = self._backup_mgr.restore_partition(
            backup_info=b_info,
            item_name=part,
            fastboot=self._fb,
            serial=self._current_device.serial if self._current_device else b_info.serial,
            dry_run=False,
        )
        shield.mark_completed(success, msg)
