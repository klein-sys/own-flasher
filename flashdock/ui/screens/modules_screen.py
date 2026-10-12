"""
FlashDock — Root Modules & Module Library Screen (macOS Big Sur UI).

Provides:
* 📱 Tab 1: Installed Modules (Device) — Inspect, enable, disable, remove modules,
  and emergency bootloop recovery (Disable All Modules kill-switch, Safe Mode reboot).
* 📚 Tab 2: Module Library (Offline Repository & Catalog) — Manage stored offline module ZIPs
  in data/modules/, 1-click install to connected phone, import module ZIPs, and browse
  curated essential root modules (Play Integrity Fix, Shamiko, Zygisk Next, etc.).

Spec references: Section 12, Section 15, Section 16, Section 29.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from flashdock.constants import MODULES_DIR
from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.core.modules import ModuleInfo, ModuleInspectionResult, ModuleManager
from flashdock.core.repository import RepositoryManager, StoredItem
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.ui.icon_assets import create_icon_label, get_icon
from flashdock.ui.widgets.flash_shield import FlashShieldDialog

log = get_logger(__name__)


# Curated catalog of essential root modules with official repository URLs
RECOMMENDED_MODULES = [
    {
        "name": "Play Integrity Fix",
        "author": "chiteroman",
        "tag": "Google Play & SafetyNet",
        "desc": "Fixes MEETS_DEVICE_INTEGRITY and SafetyNet verdicts on rooted devices to keep banking apps & Google Wallet working.",
        "url": "https://github.com/chiteroman/PlayIntegrityFix/releases",
    },
    {
        "name": "Shamiko",
        "author": "LSPosed Devs",
        "tag": "Advanced Root Hiding",
        "desc": "Zygisk-based module to hide Magisk/KernelSU root and unofficial processes from sensitive applications.",
        "url": "https://github.com/LSPosed/LSPosed.github.io/releases",
    },
    {
        "name": "Zygisk Next",
        "author": "Dr-TSNG",
        "tag": "KernelSU & APatch Zygisk",
        "desc": "Standalone Zygisk implementation for KernelSU and APatch environments, enabling standard Zygisk modules.",
        "url": "https://github.com/Dr-TSNG/ZygiskNext/releases",
    },
    {
        "name": "Magisk Bootloop Protector",
        "author": "HuskyDG",
        "tag": "Bootloop Insurance",
        "desc": "Automatically disables all Magisk modules if system boot fails or freezes repeatedly, saving your device from bootloops.",
        "url": "https://github.com/HuskyDG/MagiskBootloopProtector/releases",
    },
    {
        "name": "Audio Modification Library (AML)",
        "author": "Zackptg5",
        "tag": "Audio Mod Bridge",
        "desc": "Combines multiple audio modifications (ViPER4Android, Dolby, JamesDSP) into a unified audio policy framework.",
        "url": "https://github.com/Zackptg5/Audio-Modification-Library/releases",
    },
    {
        "name": "Systemless Hosts",
        "author": "Magisk / topjohnwu",
        "tag": "Ad-Blocking",
        "desc": "Redirects /system/etc/hosts to /data without altering system partitions, enabling root ad-blockers like AdAway.",
        "url": "https://github.com/topjohnwu/Magisk/releases",
    },
]


# ---------------------------------------------------------------------------
# Module Inspection Dialog
# ---------------------------------------------------------------------------

class ModuleInspectorDialog(QDialog):
    """Shows module metadata and risk warnings before installation with macOS Big Sur aesthetics."""

    def __init__(self, inspection: ModuleInspectionResult, zip_path: Path, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Module Pre-Install Inspection")
        self.setMinimumSize(500, 440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        info = inspection.module_info
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title_row.addWidget(create_icon_label("modules", 22))
        title = QLabel(f"{info.name if info else zip_path.name}")
        title.setProperty("cssClass", "heading")
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        if info:
            meta_frame = QFrame()
            meta_frame.setProperty("cssClass", "card")
            mf_layout = QVBoxLayout(meta_frame)
            mf_layout.setSpacing(8)

            lbl_id = QLabel(f"<b>Module ID:</b> {info.id}")
            lbl_ver = QLabel(f"<b>Version:</b> {info.version} (code {info.version_code})")
            lbl_auth = QLabel(f"<b>Author:</b> {info.author or 'Unknown'}")
            lbl_desc = QLabel(f"<b>Description:</b> {info.description or 'None'}")
            lbl_desc.setWordWrap(True)
            lbl_size = QLabel(f"<b>Archive Size:</b> {inspection.total_size_bytes // 1024} KB ({inspection.file_count} files)")

            mf_layout.addWidget(lbl_id)
            mf_layout.addWidget(lbl_ver)
            mf_layout.addWidget(lbl_auth)
            mf_layout.addWidget(lbl_desc)
            mf_layout.addWidget(lbl_size)

            layout.addWidget(meta_frame)

        # Warnings banner if risks detected
        if inspection.warnings:
            warn_frame = QFrame()
            warn_frame.setProperty("cssClass", "danger_banner")
            wf_layout = QVBoxLayout(warn_frame)
            wf_layout.setSpacing(6)

            wf_title_row = QHBoxLayout()
            wf_title_row.setSpacing(8)
            wf_title_row.addWidget(create_icon_label("warning", 18))
            wf_title = QLabel("POTENTIAL RISKS DETECTED")
            wf_title.setProperty("cssClass", "error")
            wf_title_row.addWidget(wf_title)
            wf_title_row.addStretch()
            wf_layout.addLayout(wf_title_row)

            for w in inspection.warnings:
                item = QLabel(f"• {w}")
                item.setWordWrap(True)
                item.setProperty("cssClass", "error")
                wf_layout.addWidget(item)

            layout.addWidget(warn_frame)

        layout.addStretch()

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("cssClass", "secondary")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        btn_row.addStretch()

        install_btn = QPushButton("Install Module")
        install_btn.setProperty("cssClass", "primary")
        install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        install_btn.clicked.connect(self.accept)
        btn_row.addWidget(install_btn)

        layout.addLayout(btn_row)


# ---------------------------------------------------------------------------
# Modules & Library Screen
# ---------------------------------------------------------------------------

class ModulesScreen(QWidget):
    """The root modules management and offline library screen."""

    def __init__(
        self,
        device_mgr: DeviceManager,
        adb: ADB,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._device_mgr = device_mgr
        self._adb = adb
        self._module_mgr = ModuleManager()
        self._repo_mgr = RepositoryManager()
        self._current_device: Optional[DeviceInfo] = None
        self._cached_modules: list[ModuleInfo] = []

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(14)

        # Main Header
        header_row = QHBoxLayout()
        header_row.setSpacing(12)
        header_icon = create_icon_label("modules", 24)
        header_row.addWidget(header_icon)

        header_col = QVBoxLayout()
        header_col.setSpacing(2)

        title = QLabel("Root Modules & Library (Magisk · KernelSU · APatch)")
        title.setProperty("cssClass", "heading")
        header_col.addWidget(title)

        self._subtitle = QLabel("Manage installed device modules, browse offline library ZIPs, and configure bootloop safety.")
        self._subtitle.setProperty("cssClass", "muted")
        header_col.addWidget(self._subtitle)
        header_row.addLayout(header_col, 1)

        layout.addLayout(header_row)

        # Tabs: Tab 1 = Installed Modules, Tab 2 = Module Library
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        self._tab_installed = QWidget()
        self._tab_library = QWidget()

        self._setup_installed_tab()
        self._setup_library_tab()

        self._tabs.addTab(self._tab_installed, get_icon("phone", 16), "Installed Modules (Device)")
        self._tabs.addTab(self._tab_library, get_icon("book", 16), "Module Library (Offline & Catalog)")

        layout.addWidget(self._tabs, 1)

    # -----------------------------------------------------------------------
    # Tab 1: Installed Modules on Device
    # -----------------------------------------------------------------------

    def _setup_installed_tab(self) -> None:
        layout = QVBoxLayout(self._tab_installed)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Top Action Bar Card
        bar_frame = QFrame()
        bar_frame.setProperty("cssClass", "card")
        bar_layout = QHBoxLayout(bar_frame)
        bar_layout.setContentsMargins(12, 10, 12, 10)
        bar_layout.setSpacing(10)

        self._btn_install = QPushButton("Install Module ZIP...")
        self._btn_install.setIcon(get_icon("plus", 14))
        self._btn_install.setProperty("cssClass", "primary")
        self._btn_install.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_install.clicked.connect(self._on_install_module_clicked)
        bar_layout.addWidget(self._btn_install)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setIcon(get_icon("refresh", 14))
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh_modules)
        bar_layout.addWidget(refresh_btn)

        bar_layout.addStretch()

        # Emergency tools
        self._btn_emergency_disable = QPushButton("Disable All Modules")
        self._btn_emergency_disable.setIcon(get_icon("warning", 14))
        self._btn_emergency_disable.setProperty("cssClass", "warning")
        self._btn_emergency_disable.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_emergency_disable.setToolTip("Emergency kill-switch to recover phone from bootlooping modules.")
        self._btn_emergency_disable.clicked.connect(self._on_emergency_disable)
        bar_layout.addWidget(self._btn_emergency_disable)

        self._btn_safe_mode = QPushButton("Safe Mode Reboot")
        self._btn_safe_mode.setIcon(get_icon("shield", 14))
        self._btn_safe_mode.setProperty("cssClass", "danger")
        self._btn_safe_mode.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_safe_mode.clicked.connect(self._on_safe_mode_clicked)
        bar_layout.addWidget(self._btn_safe_mode)

        layout.addWidget(bar_frame)

        # Table of Installed Modules
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Module Name & ID", "Version", "Author", "Status", "Actions"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table, 1)

    # -----------------------------------------------------------------------
    # Tab 2: Module Library (Offline Repository & Curated Catalog)
    # -----------------------------------------------------------------------

    def _setup_library_tab(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Library Controls Card
        bar_frame = QFrame()
        bar_frame.setProperty("cssClass", "card")
        bar_layout = QHBoxLayout(bar_frame)
        bar_layout.setContentsMargins(12, 10, 12, 10)
        bar_layout.setSpacing(10)

        self._btn_import_lib = QPushButton("Import Module ZIP to Library...")
        self._btn_import_lib.setIcon(get_icon("plus", 14))
        self._btn_import_lib.setProperty("cssClass", "primary")
        self._btn_import_lib.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_import_lib.clicked.connect(self._on_import_to_library)
        bar_layout.addWidget(self._btn_import_lib)

        self._btn_open_lib_folder = QPushButton("Open Modules Folder")
        self._btn_open_lib_folder.setIcon(get_icon("folder", 14))
        self._btn_open_lib_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_open_lib_folder.clicked.connect(self._on_open_modules_folder)
        bar_layout.addWidget(self._btn_open_lib_folder)

        self._btn_refresh_lib = QPushButton("Refresh Library")
        self._btn_refresh_lib.setIcon(get_icon("refresh", 14))
        self._btn_refresh_lib.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_refresh_lib.clicked.connect(self.refresh_library)
        bar_layout.addWidget(self._btn_refresh_lib)

        bar_layout.addStretch()

        lib_dir_label = QLabel(f"Storage: data/modules/")
        lib_dir_label.setProperty("cssClass", "muted")
        bar_layout.addWidget(lib_dir_label)

        layout.addWidget(bar_frame)

        # Stored Modules Section Card
        stored_card = QFrame()
        stored_card.setProperty("cssClass", "card")
        sc_layout = QVBoxLayout(stored_card)
        sc_layout.setContentsMargins(14, 14, 14, 14)
        sc_layout.setSpacing(10)

        sc_title = QLabel("Stored Offline Modules")
        sc_title.setProperty("cssClass", "subheading")
        sc_layout.addWidget(sc_title)

        self._lib_table = QTableWidget()
        self._lib_table.setColumnCount(5)
        self._lib_table.setHorizontalHeaderLabels(["Module Name & ID", "Version", "Size", "Description", "Actions"])
        self._lib_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self._lib_table.horizontalHeader().resizeSection(0, 200)
        self._lib_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._lib_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._lib_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._lib_table.setAlternatingRowColors(True)
        self._lib_table.setMinimumHeight(180)
        sc_layout.addWidget(self._lib_table)

        layout.addWidget(stored_card)

        # Recommended Modules Catalog Section
        catalog_card = QFrame()
        catalog_card.setProperty("cssClass", "card")
        cc_layout = QVBoxLayout(catalog_card)
        cc_layout.setContentsMargins(14, 14, 14, 14)
        cc_layout.setSpacing(12)

        cc_title = QLabel("Recommended Root Modules Catalog")
        cc_title.setProperty("cssClass", "subheading")
        cc_layout.addWidget(cc_title)

        cc_desc = QLabel("Verified, popular modules for Android rooting environments. Click to open official GitHub release pages.")
        cc_desc.setProperty("cssClass", "muted")
        cc_layout.addWidget(cc_desc)

        for mod in RECOMMENDED_MODULES:
            row_frame = QFrame()
            row_frame.setProperty("cssClass", "card_subtle")
            rf_layout = QHBoxLayout(row_frame)
            rf_layout.setContentsMargins(12, 10, 12, 10)
            rf_layout.setSpacing(12)

            info_col = QVBoxLayout()
            info_col.setSpacing(4)

            name_row = QHBoxLayout()
            name_row.setSpacing(8)

            lbl_name = QLabel(f"<b>{mod['name']}</b> <span style='font-size: 11px; color: #8E8E93;'>by {mod['author']}</span>")
            lbl_name.setProperty("cssClass", "subheading")
            name_row.addWidget(lbl_name)

            lbl_tag = QLabel(f" {mod['tag']} ")
            lbl_tag.setProperty("cssClass", "code_text")
            name_row.addWidget(lbl_tag)
            name_row.addStretch()

            info_col.addLayout(name_row)

            lbl_d = QLabel(mod["desc"])
            lbl_d.setWordWrap(True)
            lbl_d.setProperty("cssClass", "muted")
            info_col.addWidget(lbl_d)

            rf_layout.addLayout(info_col, 1)

            btn_dl = QPushButton("Download Release")
            btn_dl.setIcon(get_icon("globe", 14))
            btn_dl.setProperty("cssClass", "secondary")
            btn_dl.setCursor(Qt.CursorShape.PointingHandCursor)
            url_to_open = mod["url"]
            btn_dl.clicked.connect(lambda _, u=url_to_open: QDesktopServices.openUrl(QUrl(u)))
            rf_layout.addWidget(btn_dl)

            cc_layout.addWidget(row_frame)

        layout.addWidget(catalog_card)
        layout.addStretch()

        scroll.setWidget(content)
        t_layout = QVBoxLayout(self._tab_library)
        t_layout.setContentsMargins(0, 0, 0, 0)
        t_layout.addWidget(scroll)

        # Initial library load
        self.refresh_library()

    # -----------------------------------------------------------------------
    # Device Loading & Installed Modules Refresh
    # -----------------------------------------------------------------------

    def load_for_device(self, device: Optional[DeviceInfo]) -> None:
        """Update screen context when device changes."""
        self._current_device = device
        if device and device.mode != "not_connected":
            root_info = f"Framework: {device.root_method.title()}" if device.is_rooted else "Not Rooted"
            self._subtitle.setText(f"{device.summary_line} · {root_info}")
        else:
            self._subtitle.setText("No device connected. Connect via USB with root to manage modules.")

        self.refresh_modules()
        self.refresh_library()

    def refresh_modules(self) -> None:
        """Scan device via ADB for installed modules."""
        serial = self._current_device.serial if self._current_device else ""
        modules = self._module_mgr.list_installed_modules(self._adb, serial=serial)
        self._cached_modules = modules
        self._table.setRowCount(len(modules))

        for row, mod in enumerate(modules):
            # Name & ID
            title_item = QTableWidgetItem(f"{mod.name}\n({mod.id})")
            self._table.setItem(row, 0, title_item)

            # Version
            self._table.setItem(row, 1, QTableWidgetItem(f"{mod.version} ({mod.version_code})"))

            # Author
            self._table.setItem(row, 2, QTableWidgetItem(mod.author or "Unknown"))

            # Status pill
            status_item = QTableWidgetItem("Enabled" if mod.enabled else "Disabled")
            status_item.setIcon(get_icon("check" if mod.enabled else "cross", 14))
            status_item.setForeground(Qt.GlobalColor.darkGreen if mod.enabled else Qt.GlobalColor.darkYellow)
            self._table.setItem(row, 3, status_item)

            # Actions cell widget
            action_widget = QWidget()
            aw_layout = QHBoxLayout(action_widget)
            aw_layout.setContentsMargins(4, 2, 4, 2)
            aw_layout.setSpacing(6)

            toggle_btn = QPushButton("Disable" if mod.enabled else "Enable")
            toggle_btn.setProperty("cssClass", "secondary")
            toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            toggle_btn.clicked.connect(lambda _, m=mod: self._on_toggle_module(m))
            aw_layout.addWidget(toggle_btn)

            remove_btn = QPushButton("Remove")
            remove_btn.setProperty("cssClass", "danger")
            remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            remove_btn.clicked.connect(lambda _, m=mod: self._on_remove_module(m))
            aw_layout.addWidget(remove_btn)

            self._table.setCellWidget(row, 4, action_widget)

    # -----------------------------------------------------------------------
    # Library Management & Flashing
    # -----------------------------------------------------------------------

    def refresh_library(self) -> None:
        """Scan local MODULES_DIR repository and populate the library table."""
        items: list[StoredItem] = self._repo_mgr.scan_modules()
        self._lib_table.setRowCount(len(items))

        for row, item in enumerate(items):
            # Name & ID
            name_cell = QTableWidgetItem(f"{item.name}\n({item.id})")
            self._lib_table.setItem(row, 0, name_cell)

            # Version
            ver_cell = QTableWidgetItem(item.version or "1.0")
            self._lib_table.setItem(row, 1, ver_cell)

            # Size
            size_cell = QTableWidgetItem(f"{item.size_mb} MB")
            self._lib_table.setItem(row, 2, size_cell)

            # Description
            desc_cell = QTableWidgetItem(item.description or "Root module ZIP archive")
            self._lib_table.setItem(row, 3, desc_cell)

            # Actions
            action_widget = QWidget()
            aw_layout = QHBoxLayout(action_widget)
            aw_layout.setContentsMargins(4, 2, 4, 2)
            aw_layout.setSpacing(6)

            btn_flash = QPushButton("Flash to Phone")
            btn_flash.setIcon(get_icon("flash", 14))
            btn_flash.setProperty("cssClass", "primary")
            btn_flash.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_flash.clicked.connect(lambda _, p=item.file_path: self._flash_zip_file(p))
            aw_layout.addWidget(btn_flash)

            btn_del = QPushButton("Delete")
            btn_del.setIcon(get_icon("trash", 14))
            btn_del.setProperty("cssClass", "danger")
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.clicked.connect(lambda _, p=item.file_path, n=item.name: self._on_delete_library_item(p, n))
            aw_layout.addWidget(btn_del)

            self._lib_table.setCellWidget(row, 4, action_widget)

    def _on_import_to_library(self) -> None:
        """Import an existing module ZIP from user computer into data/modules/."""
        zip_file, _ = QFileDialog.getOpenFileName(
            self,
            "Select Root Module ZIP to Import",
            "",
            "Module ZIP (*.zip);;All Files (*.*)",
        )
        if not zip_file:
            return

        src_path = Path(zip_file)
        inspection = self._module_mgr.inspect_module_zip(src_path)
        if not inspection.is_valid_module:
            warns = "\n".join(f"• {w}" for w in inspection.warnings)
            QMessageBox.critical(self, "Invalid Module", f"Cannot import into library:\n\n{warns}")
            return

        dest_path = MODULES_DIR / src_path.name
        try:
            shutil.copy2(src_path, dest_path)
            QMessageBox.information(
                self,
                "Module Imported",
                f"Successfully imported '{src_path.name}' into your local Module Library!",
            )
            self.refresh_library()
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", f"Could not copy module ZIP:\n\n{e}")

    def _on_open_modules_folder(self) -> None:
        """Open the local modules folder in Explorer."""
        MODULES_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(MODULES_DIR)))

    def _on_delete_library_item(self, path: Path, name: str) -> None:
        reply = QMessageBox.question(
            self,
            "Delete Module from Library?",
            f"Are you sure you want to permanently delete '{name}' ({path.name}) from your offline library?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if path.exists():
                    path.unlink()
                self.refresh_library()
            except Exception as e:
                QMessageBox.critical(self, "Delete Error", f"Could not delete module:\n\n{e}")

    def _flash_zip_file(self, zip_path: Path) -> None:
        """Inspect and install a module ZIP onto the connected device."""
        device = self._current_device
        if not device or device.mode != "system":
            QMessageBox.warning(
                self,
                "System Mode Required",
                "Please connect your phone in Android system mode with USB debugging enabled.",
            )
            return

        inspection = self._module_mgr.inspect_module_zip(zip_path)
        if not inspection.is_valid_module:
            warns = "\n".join(f"• {w}" for w in inspection.warnings)
            QMessageBox.critical(self, "Invalid Module", f"This archive is not a valid root module:\n\n{warns}")
            return

        # Show inspection preview
        inspector = ModuleInspectorDialog(inspection, zip_path, self)
        if inspector.exec() != QDialog.DialogCode.Accepted:
            return

        # Start installation under FlashShield modal
        shield = FlashShieldDialog(self)
        shield.show()
        shield.update_progress(f"Pushing and installing '{zip_path.name}'...", 40)

        ok, msg = self._module_mgr.install_module(
            zip_path=zip_path,
            adb=self._adb,
            root_framework=device.root_method or "magisk",
            serial=device.serial,
            dry_run=False,
        )
        shield.mark_completed(ok, msg)
        self.refresh_modules()

    # -----------------------------------------------------------------------
    # Installed Module Actions
    # -----------------------------------------------------------------------

    def _on_install_module_clicked(self) -> None:
        zip_file, _ = QFileDialog.getOpenFileName(
            self,
            "Select Root Module ZIP",
            "",
            "Module ZIP (*.zip);;All Files (*.*)",
        )
        if not zip_file:
            return

        self._flash_zip_file(Path(zip_file))

    def _on_toggle_module(self, mod: ModuleInfo) -> None:
        serial = self._current_device.serial if self._current_device else ""
        if mod.enabled:
            ok, msg = self._module_mgr.disable_module(mod.id, self._adb, serial=serial)
        else:
            ok, msg = self._module_mgr.enable_module(mod.id, self._adb, serial=serial)

        if ok:
            QMessageBox.information(self, "Module Updated", msg)
            self.refresh_modules()
        else:
            QMessageBox.warning(self, "Update Failed", msg)

    def _on_remove_module(self, mod: ModuleInfo) -> None:
        reply = QMessageBox.question(
            self,
            "Remove Module?",
            f"Are you sure you want to completely remove module '{mod.name}' ({mod.id}) from the phone?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            serial = self._current_device.serial if self._current_device else ""
            ok, msg = self._module_mgr.remove_module(mod.id, self._adb, serial=serial)
            if ok:
                QMessageBox.information(self, "Module Removed", msg)
                self.refresh_modules()
            else:
                QMessageBox.warning(self, "Remove Failed", msg)

    def _on_emergency_disable(self) -> None:
        reply = QMessageBox.warning(
            self,
            "Emergency: Disable All Modules?",
            "This will create a disable flag on EVERY installed root module on the device.\n\n"
            "Use this if your phone is unstable, lagging, or recovering from a module-induced soft-brick.\n\nProceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            serial = self._current_device.serial if self._current_device else ""
            ok, msg = self._module_mgr.emergency_disable_all_modules(self._adb, serial=serial)
            if ok:
                QMessageBox.information(self, "Modules Disabled", msg)
                self.refresh_modules()
            else:
                QMessageBox.warning(self, "Action Failed", msg)

    def _on_safe_mode_clicked(self) -> None:
        reply = QMessageBox.question(
            self,
            "Reboot to Safe Mode?",
            "Reboot the phone into Safe Mode?\n\n"
            "Safe Mode starts Android with all root modules and custom overlays disabled.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            serial = self._current_device.serial if self._current_device else ""
            res = self._module_mgr.reboot_safe_mode(self._adb, serial=serial)
            if res.success:
                QMessageBox.information(self, "Rebooting", "Device is rebooting to Safe Mode.")
            else:
                QMessageBox.warning(self, "Reboot Failed", f"Could not reboot to Safe Mode: {res.stderr}")
