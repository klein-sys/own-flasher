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

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
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
from flashdock.ui.widgets.flash_shield import FlashShieldDialog

log = get_logger(__name__)

# Common partitions users might want to back up
RECOMMENDED_PARTITIONS = ["boot", "recovery", "vbmeta", "init_boot", "vendor_boot"]
CRITICAL_RADIO_PARTITIONS = ["efs", "nvram", "nvdata", "modem", "persist"]


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
        title = QLabel("💼  Backup & Restore Manager")
        title.setProperty("cssClass", "heading")
        layout.addWidget(title)

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

        self._tabs.addTab(self._tab_partitions, "Partition Backup")
        self._tabs.addTab(self._tab_adb, "Full ADB Backup")
        self._tabs.addTab(self._tab_restore, "Restore Backups")

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
        efs_warn = QLabel(
            "💡 TIP: Backing up EFS / NVRAM partitions preserves your device's unique IMEI and radio calibration data."
        )
        efs_warn.setProperty("cssClass", "info_banner")
        layout.addWidget(efs_warn)

        # Checkboxes for partitions
        part_group = QFrame()
        part_group.setProperty("cssClass", "card")
        part_layout = QVBoxLayout(part_group)

        self._part_checkboxes: dict[str, QCheckBox] = {}
        all_parts = RECOMMENDED_PARTITIONS + CRITICAL_RADIO_PARTITIONS

        for p in all_parts:
            cb = QCheckBox(f"{p} partition")
            if p in ("boot", "recovery", "vbmeta"):
                cb.setChecked(True)
            self._part_checkboxes[p] = cb
            part_layout.addWidget(cb)

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

        self._btn_start_part_backup = QPushButton("▶  Start Partition Backup")
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

        note_box = QLabel(
            "⚠️  ON-PHONE ACTION REQUIRED:\n"
            "After clicking 'Start ADB Backup', unlock your phone screen and tap 'Back up my data' when prompted."
        )
        note_box.setProperty("cssClass", "warn_banner")
        layout.addWidget(note_box)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._btn_start_adb_backup = QPushButton("▶  Start ADB Backup")
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

        refresh_btn = QPushButton("🔄 Refresh Catalog")
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
        layout.addWidget(self._table, 1)

        # Action row
        btn_row = QHBoxLayout()

        self._btn_delete_backup = QPushButton("🗑️ Delete Backup")
        self._btn_delete_backup.setProperty("cssClass", "danger")
        self._btn_delete_backup.clicked.connect(self._on_delete_backup)
        btn_row.addWidget(self._btn_delete_backup)

        btn_row.addStretch()

        self._btn_restore = QPushButton("⚡ Restore Partition...")
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

        def progress_cb(part: str, idx: int, total: int):
            pct = int((idx / total) * 90)
            shield.update_progress(f"Dumping '{part}' partition ({idx}/{total})...", pct)

        try:
            info = self._backup_mgr.create_partition_backup(
                device=device,
                partitions=selected,
                adb=self._adb,
                fastboot=self._fb,
                dry_run=False,
                on_progress=progress_cb,
            )
            shield.mark_completed(True, f"Partition backup saved ({len(info.items)} partitions).")
            self.refresh_catalog()
        except Exception as e:
            shield.mark_completed(False, f"Backup error: {e}")

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

        try:
            info = self._backup_mgr.create_adb_backup(
                device=device,
                adb=self._adb,
                include_apk=include_apk,
                include_shared=include_shared,
                dry_run=False,
            )
            shield.mark_completed(True, f"ADB backup complete: {info.backup_id}")
            self.refresh_catalog()
        except Exception as e:
            shield.mark_completed(False, f"ADB backup error: {e}")

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
            f"⚠️ RESTORE WARNING:\n\n"
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
