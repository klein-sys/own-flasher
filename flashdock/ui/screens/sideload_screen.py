"""
FlashDock — Universal Sideloading & App Manager Screen (Phase 23).

Provides:
1. Interactive Drag-and-Drop Dropzone for single APKs, Split App Bundles (.xapk, .apks, .apkm),
   and Recovery OTA update ZIPs.
2. File Metadata Inspector (Package ID, Version Name/Code, Min/Target SDK, App Icon).
3. Advanced Installation Flags Checklist:
   - Grant runtime permissions (-g)
   - Allow version downgrade (-d)
   - Bypass Android 14+ Low SDK Block (--bypass-low-target-sdk-block)
   - Install for primary user (--user 0)
   - Allow test packages (-t)
4. Recovery Mode OTA Sideload tab with progress parsing and connection state validation.
5. Installed Apps Inspector & Debloater tab:
   - Filterable table (User 3rd-party apps, System Bloatware, Disabled/Frozen).
   - Quick actions: Pull APK to PC, Clear Cache & Data, Force Stop, Disable/Freeze, Uninstall.
6. Real-time streaming terminal log & upload progress bar.

Conforms to Apple HIG, macOS Big Sur / Sequoia squircle tokens, and HyperOS 2.0 ergonomics.
Zero raw emojis — 100% vector SVG icons.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Qt, Signal, Slot
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.tools.sideload import (
    ApkMetadata,
    SideloadAppItem,
    SideloadFlags,
    SideloadManager,
    extract_apk_metadata,
)
from flashdock.ui.icon_assets import create_icon_label, get_icon, get_icon_pixmap

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Background Worker for Non-Blocking Execution
# ---------------------------------------------------------------------------

class SideloadWorker(QThread):
    """Background worker executing ADB installation, sideload, and debloat actions."""

    progress_updated = Signal(int, str)
    log_emitted = Signal(str, str)         # level, message
    operation_finished = Signal(bool, str)  # success, message
    packages_loaded = Signal(list)          # list[SideloadAppItem]

    def __init__(
        self,
        manager: SideloadManager,
        action: str,
        params: dict,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.manager = manager
        self.action = action
        self.params = params

    def run(self) -> None:
        try:
            if self.action == "install_single":
                apk_path = self.params["path"]
                flags = self.params["flags"]
                serial = self.params.get("serial", "")
                self.log_emitted.emit("INFO", f"Starting installation for {Path(apk_path).name}...")
                ok, msg = self.manager.install_apk(
                    apk_path,
                    flags=flags,
                    serial=serial,
                    progress_cb=lambda s: self.log_emitted.emit("INFO", s),
                )
                self.operation_finished.emit(ok, msg)

            elif self.action == "install_split":
                bundle_path = self.params["path"]
                flags = self.params["flags"]
                serial = self.params.get("serial", "")
                self.log_emitted.emit("INFO", f"Starting split bundle deployment for {Path(bundle_path).name}...")
                ok, msg = self.manager.install_split_bundle(
                    bundle_path,
                    flags=flags,
                    serial=serial,
                    progress_cb=lambda s: self.log_emitted.emit("INFO", s),
                )
                self.operation_finished.emit(ok, msg)

            elif self.action == "sideload_ota":
                zip_path = self.params["path"]
                serial = self.params.get("serial", "")
                self.log_emitted.emit("INFO", f"Starting Recovery OTA sideload: {Path(zip_path).name}...")

                def _prog(pct: int, st: str) -> None:
                    self.progress_updated.emit(pct, st)
                    self.log_emitted.emit("INFO", f"[{pct}%] {st}")

                ok, msg = self.manager.sideload_ota_zip(
                    zip_path,
                    serial=serial,
                    progress_cb=_prog,
                )
                self.operation_finished.emit(ok, msg)

            elif self.action == "list_packages":
                serial = self.params.get("serial", "")
                filter_type = self.params.get("filter_type", "3rd_party")
                self.log_emitted.emit("INFO", f"Enumerating installed packages ({filter_type})...")
                pkgs = self.manager.list_installed_packages(serial=serial, filter_type=filter_type)
                self.packages_loaded.emit(pkgs)
                self.operation_finished.emit(True, f"Loaded {len(pkgs)} packages.")

            elif self.action == "manage_package":
                pkg = self.params["package_name"]
                act = self.params["pkg_action"]
                serial = self.params.get("serial", "")
                dest = self.params.get("dest_dir", None)
                self.log_emitted.emit("INFO", f"Executing {act} on {pkg}...")
                ok, msg = self.manager.manage_package(pkg, act, serial=serial, dest_dir=dest)
                self.operation_finished.emit(ok, msg)

        except Exception as exc:
            log.exception("Error during sideload worker execution: %s", exc)
            self.log_emitted.emit("ERROR", str(exc))
            self.operation_finished.emit(False, str(exc))


# ---------------------------------------------------------------------------
# Interactive Squircle Dropzone Widget
# ---------------------------------------------------------------------------

class FileDropZone(QFrame):
    """Large modern drag-and-drop squircle card with file picker support."""

    file_selected = Signal(str)

    def __init__(
        self,
        title: str = "Drop APK, Split XAPK, or OTA ZIP here",
        subtitle: str = "or click to browse from computer (Supports .apk, .xapk, .apks, .apkm, .zip)",
        file_filters: str = "Android Packages (*.apk *.xapk *.apks *.apkm *.zip);;All Files (*.*)",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.file_filters = file_filters
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(6)

        # Center icon chip
        self.icon_chip = QFrame()
        self.icon_chip.setFixedSize(40, 40)
        self.icon_chip.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0A84FF, stop:1 #0056B3);
            border-radius: 20px;
            border: none;
        """)
        chip_lay = QHBoxLayout(self.icon_chip)
        chip_lay.setContentsMargins(0, 0, 0, 0)
        chip_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_lbl = QLabel()
        self.icon_lbl.setPixmap(get_icon_pixmap("box", width=20, height=20, color="#FFFFFF"))
        chip_lay.addWidget(self.icon_lbl)
        layout.addWidget(self.icon_chip, 0, Qt.AlignmentFlag.AlignCenter)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("font-size: 14px; font-weight: 600; color: #E6EDF3;")
        self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_lbl)

        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setStyleSheet("font-size: 11px; color: #8E8E93;")
        self.sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.sub_lbl)

        self._apply_normal_style("dark")

    def _apply_normal_style(self, theme: str) -> None:
        if theme == "light":
            self.setStyleSheet("""
                QFrame {
                    background-color: #ECEFF4;
                    border: 2px dashed #CBD1DC;
                    border-radius: 16px;
                }
                QFrame:hover {
                    background-color: #F4F6F9;
                    border-color: #007AFF;
                }
            """)
            self.title_lbl.setStyleSheet("font-size: 14px; font-weight: 600; color: #1C2024; background: transparent;")
            self.sub_lbl.setStyleSheet("font-size: 11px; color: #5A6572; background: transparent;")
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #1A212E;
                    border: 2px dashed rgba(255, 255, 255, 0.15);
                    border-radius: 16px;
                }
                QFrame:hover {
                    background-color: #222C3D;
                    border-color: #0A84FF;
                }
            """)
            self.title_lbl.setStyleSheet("font-size: 14px; font-weight: 600; color: #E6EDF3; background: transparent;")
            self.sub_lbl.setStyleSheet("font-size: 11px; color: #8B949E; background: transparent;")

    def _apply_drag_style(self) -> None:
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(10, 132, 255, 0.15);
                border: 2px solid #0A84FF;
                border-radius: 16px;
            }
        """)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                ext = Path(url.toLocalFile()).suffix.lower()
                if ext in (".apk", ".xapk", ".apks", ".apkm", ".zip"):
                    event.acceptProposedAction()
                    self._apply_drag_style()
                    return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._apply_normal_style("dark")

    def dropEvent(self, event: QDropEvent) -> None:
        self._apply_normal_style("dark")
        for url in event.mimeData().urls():
            local_file = url.toLocalFile()
            if os.path.isfile(local_file):
                event.acceptProposedAction()
                self.file_selected.emit(local_file)
                return
        event.ignore()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            chosen, _ = QFileDialog.getOpenFileName(
                self,
                "Select Android Package or Archive",
                "",
                self.file_filters,
            )
            if chosen:
                self.file_selected.emit(chosen)
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Sideload Screen Widget
# ---------------------------------------------------------------------------

class SideloadScreen(QWidget):
    """Main Universal Sideloading & App Manager screen (Phase 23)."""

    navigate_to_page = Signal(int)

    def __init__(
        self,
        device_mgr: Optional[DeviceManager] = None,
        adb: Optional[ADB] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._device_mgr = device_mgr
        self._adb = adb or (device_mgr.adb if device_mgr else ADB())
        self._manager = SideloadManager(adb=self._adb)

        self._current_device: Optional[DeviceInfo] = None
        self._device_sdk = 0
        self._selected_file_path = ""
        self._cached_meta: Optional[ApkMetadata] = None
        self._worker: Optional[SideloadWorker] = None
        self._current_theme = "dark"

        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 16, 24, 16)
        root_layout.setSpacing(14)

        # ---- Top Header Bar ----
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(12)

        icon_box = QFrame()
        icon_box.setFixedSize(36, 36)
        icon_box.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00E5FF, stop:1 #0097A7);
            border-radius: 18px;
            border: none;
        """)
        ib_lay = QHBoxLayout(icon_box)
        ib_lay.setContentsMargins(0, 0, 0, 0)
        ib_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ib_lbl = QLabel()
        ib_lbl.setPixmap(get_icon_pixmap("box", width=20, height=20, color="#FFFFFF"))
        ib_lay.addWidget(ib_lbl)
        header_row.addWidget(icon_box)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("Universal Sideloading & App Manager")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #E6EDF3;")
        desc_lbl = QLabel("Install APKs, Split Bundles (.xapk), bypass Android 14+ restrictions, & recovery sideload")
        desc_lbl.setStyleSheet("font-size: 11px; color: #8E8E93;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(desc_lbl)
        header_row.addLayout(title_box, 1)

        # Device connection chip
        self._dev_chip = QLabel("No Device Connected")
        self._dev_chip.setStyleSheet("""
            font-size: 11px; font-weight: 600; padding: 6px 12px; border-radius: 10px;
            background-color: rgba(255, 69, 58, 0.15); color: #FF453A; border: 1px solid rgba(255, 69, 58, 0.3);
        """)
        header_row.addWidget(self._dev_chip)

        root_layout.addLayout(header_row)

        # ---- Tab Widget ----
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        self._tab_install = QWidget()
        self._tab_recovery = QWidget()
        self._tab_apps = QWidget()

        self._setup_install_tab()
        self._setup_recovery_tab()
        self._setup_apps_tab()

        self._tabs.addTab(self._tab_install, "Install Packages & Bundles")
        self._tabs.addTab(self._tab_recovery, "Recovery OTA Sideload")
        self._tabs.addTab(self._tab_apps, "Installed Apps & Debloater")

        root_layout.addWidget(self._tabs, 1)

        # ---- Global Progress & Log Footer ----
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                background: rgba(255, 255, 255, 0.05);
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0A84FF, stop:1 #00E5FF);
                border-radius: 4px;
            }
        """)
        root_layout.addWidget(self._progress_bar)

        self._log_terminal = QPlainTextEdit()
        self._log_terminal.setReadOnly(True)
        self._log_terminal.setMaximumHeight(90)
        self._log_terminal.setPlaceholderText("Workstation streaming telemetry log ready...")
        self._log_terminal.setStyleSheet("""
            QPlainTextEdit {
                font-family: Consolas, 'SF Mono', monospace;
                font-size: 11px;
                background-color: #0D1117;
                color: #58A6FF;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 6px;
            }
        """)
        root_layout.addWidget(self._log_terminal)

    # -----------------------------------------------------------------------
    # Tab 1: Install Packages & Bundles
    # -----------------------------------------------------------------------

    def _setup_install_tab(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)

        # 1. Dropzone
        self._dropzone = FileDropZone(
            title="Drop APK, Split Bundle (.xapk, .apks), or ZIP here",
            subtitle="or click to browse from local workstation",
            file_filters="Android Packages (*.apk *.xapk *.apks *.apkm *.zip);;All Files (*.*)",
        )
        self._dropzone.file_selected.connect(self._on_file_selected)
        lay.addWidget(self._dropzone)

        # 2. Metadata Card (Visible once file selected)
        self._meta_card = QFrame()
        self._meta_card.setStyleSheet("""
            QFrame {
                background-color: #161D28;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 14px;
                padding: 10px;
            }
        """)
        mc_lay = QHBoxLayout(self._meta_card)
        mc_lay.setContentsMargins(12, 10, 12, 10)
        mc_lay.setSpacing(14)

        # App Icon Frame
        self._app_icon_lbl = QLabel()
        self._app_icon_lbl.setFixedSize(54, 54)
        self._app_icon_lbl.setStyleSheet("""
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        """)
        self._app_icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._app_icon_lbl.setPixmap(get_icon_pixmap("box", width=32, height=32, color="#0A84FF"))
        mc_lay.addWidget(self._app_icon_lbl)

        # Info column
        info_col = QVBoxLayout()
        info_col.setSpacing(4)
        self._meta_title_lbl = QLabel("No package loaded")
        self._meta_title_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #FFFFFF;")
        self._meta_pkg_lbl = QLabel("com.example.app")
        self._meta_pkg_lbl.setStyleSheet("font-size: 11px; font-family: Consolas, monospace; color: #8E8E93;")
        self._meta_details_lbl = QLabel("Size: -- • Version: -- • Min SDK: --")
        self._meta_details_lbl.setStyleSheet("font-size: 11px; color: #0A84FF;")
        info_col.addWidget(self._meta_title_lbl)
        info_col.addWidget(self._meta_pkg_lbl)
        info_col.addWidget(self._meta_details_lbl)
        mc_lay.addLayout(info_col, 1)

        # Clear button
        btn_clear_file = QPushButton("Change")
        btn_clear_file.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear_file.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 11px;
                color: #E6EDF3;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.12);
            }
        """)
        btn_clear_file.clicked.connect(self._browse_file)
        mc_lay.addWidget(btn_clear_file)

        lay.addWidget(self._meta_card)
        self._meta_card.setVisible(False)

        # 3. Installation Flags Checklist Card
        flags_card = QFrame()
        flags_card.setStyleSheet("""
            QFrame {
                background-color: #161D28;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 14px;
            }
        """)
        fc_lay = QVBoxLayout(flags_card)
        fc_lay.setContentsMargins(14, 12, 14, 12)
        fc_lay.setSpacing(10)

        fc_title = QLabel("Advanced Installation Options & Bypasses")
        fc_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #E6EDF3;")
        fc_lay.addWidget(fc_title)

        grid = QHBoxLayout()
        grid.setSpacing(18)

        col1 = QVBoxLayout()
        col1.setSpacing(8)
        self._chk_permissions = QCheckBox("Grant all runtime permissions automatically (-g)")
        self._chk_permissions.setChecked(True)
        self._chk_downgrade = QCheckBox("Allow version downgrade (-d)")
        self._chk_downgrade.setChecked(True)
        self._chk_reinstall = QCheckBox("Reinstall existing application (-r)")
        self._chk_reinstall.setChecked(True)
        col1.addWidget(self._chk_permissions)
        col1.addWidget(self._chk_downgrade)
        col1.addWidget(self._chk_reinstall)
        grid.addLayout(col1, 1)

        col2 = QVBoxLayout()
        col2.setSpacing(8)
        self._chk_bypass_low_sdk = QCheckBox("Bypass Android 14+ Low SDK block (--bypass-low-target-sdk-block)")
        self._chk_bypass_low_sdk.setToolTip("Mandatory to force-install legacy apps blocked by Google Play Protect on Android 14+")
        self._chk_bypass_low_sdk.setStyleSheet("color: #FF9F0A; font-weight: 600;")
        self._chk_user_0 = QCheckBox("Install for primary user only (--user 0)")
        self._chk_test = QCheckBox("Allow test packages (-t)")
        col2.addWidget(self._chk_bypass_low_sdk)
        col2.addWidget(self._chk_user_0)
        col2.addWidget(self._chk_test)
        grid.addLayout(col2, 1)

        fc_lay.addLayout(grid)
        lay.addWidget(flags_card)

        # 4. Install Trigger Button
        self._btn_install = QPushButton("Install Package to Target Device")
        self._btn_install.setIcon(get_icon("play", 16, color="#FFFFFF"))
        self._btn_install.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_install.setFixedHeight(42)
        self._btn_install.setEnabled(False)
        self._btn_install.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0A84FF, stop:1 #0056B3);
                border: 1px solid #0A84FF;
                border-radius: 12px;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover:enabled {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1F90FF, stop:1 #0066D6);
            }
            QPushButton:disabled {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.08);
                color: #6E7681;
            }
        """)
        self._btn_install.clicked.connect(self._on_install_clicked)
        lay.addWidget(self._btn_install)

        lay.addStretch(1)
        scroll.setWidget(content)
        vbox = QVBoxLayout(self._tab_install)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(scroll)

    # -----------------------------------------------------------------------
    # Tab 2: Recovery OTA Sideload
    # -----------------------------------------------------------------------

    def _setup_recovery_tab(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)

        # Status & Instructions Card
        rec_card = QFrame()
        rec_card.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 159, 10, 0.08);
                border: 1px solid rgba(255, 159, 10, 0.25);
                border-radius: 14px;
                padding: 10px;
            }
        """)
        rc_lay = QVBoxLayout(rec_card)
        rc_lay.setSpacing(8)

        rc_title = QHBoxLayout()
        rc_title.addWidget(create_icon_label("warning", 16, color="#FF9F0A"))
        rc_t_lbl = QLabel("Recovery Mode OTA / ROM Sideload Protocol")
        rc_t_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #FF9F0A;")
        rc_title.addWidget(rc_t_lbl)
        rc_title.addStretch()

        self._btn_reboot_recovery = QPushButton("Reboot Device to Recovery")
        self._btn_reboot_recovery.setIcon(get_icon("refresh", 12, color="#FFFFFF"))
        self._btn_reboot_recovery.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_reboot_recovery.setStyleSheet("""
            QPushButton {
                background: #FF9F0A; color: #000000; font-weight: 700; font-size: 11px;
                padding: 4px 10px; border-radius: 6px; border: none;
            }
            QPushButton:hover { background: #FFAA26; }
        """)
        self._btn_reboot_recovery.clicked.connect(self._on_reboot_recovery_clicked)
        rc_title.addWidget(self._btn_reboot_recovery)

        rc_lay.addLayout(rc_title)

        rc_msg = QLabel(
            "Push official OTA update ZIPs or custom ROM/recovery packages directly to devices in Recovery or Sideload mode.\n"
            "1. Enter recovery menu -> select 'Apply update from ADB' / 'ADB Sideload'.\n"
            "2. Select or drop your update ZIP file below and click 'Start Recovery Sideload'."
        )
        rc_msg.setWordWrap(True)
        rc_msg.setStyleSheet("font-size: 11px; color: #CBD1DC; line-height: 1.3;")
        rc_lay.addWidget(rc_msg)
        lay.addWidget(rec_card)

        # Dropzone for OTA ZIP
        self._dropzone_recovery = FileDropZone(
            title="Drop Recovery OTA ZIP package here",
            subtitle="Supports signed OTA update.zip, custom ROMs, or kernel recovery archives",
            file_filters="Recovery Update Packages (*.zip);;All Files (*.*)",
        )
        self._dropzone_recovery.file_selected.connect(self._on_recovery_file_selected)
        lay.addWidget(self._dropzone_recovery)

        # Selected OTA label
        self._lbl_selected_ota = QLabel("No OTA ZIP package selected.")
        self._lbl_selected_ota.setStyleSheet("font-size: 12px; color: #8E8E93;")
        lay.addWidget(self._lbl_selected_ota)

        # Trigger Sideload Button
        self._btn_sideload_ota = QPushButton("Start Recovery Sideload (adb sideload)")
        self._btn_sideload_ota.setIcon(get_icon("play", 16, color="#FFFFFF"))
        self._btn_sideload_ota.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_sideload_ota.setFixedHeight(42)
        self._btn_sideload_ota.setEnabled(False)
        self._btn_sideload_ota.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #FF9F0A, stop:1 #D35400);
                border: 1px solid #FF9F0A;
                border-radius: 12px;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover:enabled {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #FFAA26, stop:1 #E65C00);
            }
            QPushButton:disabled {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.08);
                color: #6E7681;
            }
        """)
        self._btn_sideload_ota.clicked.connect(self._on_sideload_ota_clicked)
        lay.addWidget(self._btn_sideload_ota)

        lay.addStretch(1)
        scroll.setWidget(content)
        vbox = QVBoxLayout(self._tab_recovery)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(scroll)

    # -----------------------------------------------------------------------
    # Tab 3: Installed Apps & Debloater
    # -----------------------------------------------------------------------

    def _setup_apps_tab(self) -> None:
        lay = QVBoxLayout(self._tab_apps)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        # Filter bar
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Filter packages by name, package ID, or keyword...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._filter_package_table)
        filter_row.addWidget(self._search_input, 1)

        self._btn_filter_3rd = QPushButton("Third-Party (User)")
        self._btn_filter_3rd.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_filter_3rd.setCheckable(True)
        self._btn_filter_3rd.setChecked(True)
        self._btn_filter_3rd.clicked.connect(lambda: self._load_packages("3rd_party"))
        filter_row.addWidget(self._btn_filter_3rd)

        self._btn_filter_system = QPushButton("System Packages")
        self._btn_filter_system.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_filter_system.setCheckable(True)
        self._btn_filter_system.clicked.connect(lambda: self._load_packages("system"))
        filter_row.addWidget(self._btn_filter_system)

        self._btn_filter_disabled = QPushButton("Disabled / Frozen")
        self._btn_filter_disabled.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_filter_disabled.setCheckable(True)
        self._btn_filter_disabled.clicked.connect(lambda: self._load_packages("disabled"))
        filter_row.addWidget(self._btn_filter_disabled)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.setIcon(get_icon("refresh", 12))
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.clicked.connect(self._refresh_current_package_filter)
        filter_row.addWidget(btn_refresh)

        lay.addLayout(filter_row)

        # Packages Table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Package Name", "Category", "Status", "Remote APK Path"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet("""
            QTableWidget {
                background-color: #121824;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
                gridline-color: rgba(255, 255, 255, 0.05);
            }
            QHeaderView::section {
                background-color: #161D28;
                color: #8E8E93;
                font-size: 11px;
                font-weight: 700;
                padding: 6px;
                border: none;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        self._table.itemSelectionChanged.connect(self._on_table_selection_changed)
        lay.addWidget(self._table, 1)

        # Action Buttons Row
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self._btn_pull = QPushButton("Extract / Pull APK to PC")
        self._btn_pull.setIcon(get_icon("downloads", 12))
        self._btn_pull.setEnabled(False)
        self._btn_pull.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_pull.clicked.connect(lambda: self._execute_pkg_action("pull"))
        action_row.addWidget(self._btn_pull)

        self._btn_clear_data = QPushButton("Clear Cache & Data")
        self._btn_clear_data.setIcon(get_icon("trash", 12))
        self._btn_clear_data.setEnabled(False)
        self._btn_clear_data.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_clear_data.clicked.connect(lambda: self._execute_pkg_action("clear"))
        action_row.addWidget(self._btn_clear_data)

        self._btn_force_stop = QPushButton("Force Stop")
        self._btn_force_stop.setIcon(get_icon("power", 12))
        self._btn_force_stop.setEnabled(False)
        self._btn_force_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_force_stop.clicked.connect(lambda: self._execute_pkg_action("force_stop"))
        action_row.addWidget(self._btn_force_stop)

        self._btn_toggle_disable = QPushButton("Disable / Freeze")
        self._btn_toggle_disable.setIcon(get_icon("lock", 12))
        self._btn_toggle_disable.setEnabled(False)
        self._btn_toggle_disable.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_toggle_disable.clicked.connect(self._toggle_disable_selected)
        action_row.addWidget(self._btn_toggle_disable)

        self._btn_uninstall = QPushButton("Uninstall Package")
        self._btn_uninstall.setIcon(get_icon("cross", 12, color="#FF453A"))
        self._btn_uninstall.setEnabled(False)
        self._btn_uninstall.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_uninstall.setStyleSheet("""
            QPushButton:enabled { color: #FF453A; font-weight: 600; }
        """)
        self._btn_uninstall.clicked.connect(lambda: self._execute_pkg_action("uninstall"))
        action_row.addWidget(self._btn_uninstall)

        action_row.addStretch(1)
        lay.addLayout(action_row)

        self._cached_package_items: list[SideloadAppItem] = []

    # -----------------------------------------------------------------------
    # Logic & Event Handlers
    # -----------------------------------------------------------------------

    def load_for_device(self, info: Optional[DeviceInfo]) -> None:
        """Invoked when switching to this screen or device state changes."""
        self._current_device = info
        serial = info.serial if info else ""
        if info and info.mode != "not_connected":
            dev_name = getattr(info, "display_name", None) or info.model or info.device or "Device"
            self._dev_chip.setText(f"{dev_name} [{info.mode.upper()}]")
            self._dev_chip.setStyleSheet("""
                font-size: 11px; font-weight: 600; padding: 6px 12px; border-radius: 10px;
                background-color: rgba(48, 209, 88, 0.15); color: #30D158; border: 1px solid rgba(48, 209, 88, 0.3);
            """)
            self._device_sdk = self._manager.get_device_sdk(serial=serial)
            if self._device_sdk >= 34:
                self._chk_bypass_low_sdk.setChecked(True)
                self._append_log("INFO", f"Android 14+ (SDK {self._device_sdk}) detected: Low SDK bypass auto-enabled.")
            self._update_button_states()
        else:
            self._dev_chip.setText("No Device Connected")
            self._dev_chip.setStyleSheet("""
                font-size: 11px; font-weight: 600; padding: 6px 12px; border-radius: 10px;
                background-color: rgba(255, 69, 58, 0.15); color: #FF453A; border: 1px solid rgba(255, 69, 58, 0.3);
            """)
            self._update_button_states()

    def _update_button_states(self) -> None:
        has_device = bool(self._current_device and self._current_device.mode != "not_connected")
        has_file = bool(self._selected_file_path and os.path.isfile(self._selected_file_path))
        self._btn_install.setEnabled(has_device and has_file)
        self._btn_sideload_ota.setEnabled(has_device and bool(getattr(self, "_selected_ota_path", "")))

    @Slot(str)
    def _on_file_selected(self, file_path: str) -> None:
        if not os.path.isfile(file_path):
            return
        self._selected_file_path = file_path
        self._append_log("INFO", f"Inspecting package: {Path(file_path).name}...")

        try:
            meta = extract_apk_metadata(file_path)
            self._cached_meta = meta

            self._meta_title_lbl.setText(meta.app_label or Path(file_path).stem)
            self._meta_pkg_lbl.setText(meta.package_name)

            type_label = "Split Bundle (.xapk)" if meta.is_split else "Single APK"
            splits_info = f" ({len(meta.split_names)} splits)" if meta.split_names else ""
            details = f"Size: {meta.file_size_mb:.2f} MB • {type_label}{splits_info} • Min SDK: {meta.min_sdk or 'N/A'}"
            if meta.version_name:
                details += f" • v{meta.version_name}"
            self._meta_details_lbl.setText(details)

            # Icon rendering
            if meta.icon_bytes:
                pix = QPixmap()
                pix.loadFromData(meta.icon_bytes)
                if not pix.isNull():
                    self._app_icon_lbl.setPixmap(pix.scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                else:
                    self._app_icon_lbl.setPixmap(get_icon_pixmap("box", width=32, height=32, color="#0A84FF"))
            else:
                self._app_icon_lbl.setPixmap(get_icon_pixmap("box", width=32, height=32, color="#0A84FF"))

            self._meta_card.setVisible(True)
            self._update_button_states()
            self._append_log("SUCCESS", f"Package verified: {meta.summary_line}")

        except Exception as exc:
            self._append_log("ERROR", f"Failed to extract metadata: {exc}")
            QMessageBox.warning(self, "Metadata Extraction Error", f"Could not inspect package:\n{exc}")

    def _browse_file(self) -> None:
        chosen, _ = QFileDialog.getOpenFileName(
            self,
            "Select Android Package or Archive",
            "",
            "Android Packages (*.apk *.xapk *.apks *.apkm *.zip);;All Files (*.*)",
        )
        if chosen:
            self._on_file_selected(chosen)

    @Slot()
    def _on_install_clicked(self) -> None:
        if not self._selected_file_path or not os.path.isfile(self._selected_file_path):
            return

        flags = SideloadFlags(
            grant_permissions=self._chk_permissions.isChecked(),
            allow_downgrade=self._chk_downgrade.isChecked(),
            reinstall=self._chk_reinstall.isChecked(),
            bypass_low_sdk_block=self._chk_bypass_low_sdk.isChecked(),
            allow_test_packages=self._chk_test.isChecked(),
            install_user_0=self._chk_user_0.isChecked(),
        )

        serial = self._current_device.serial if self._current_device else ""
        is_split = (self._cached_meta and self._cached_meta.is_split) or (Path(self._selected_file_path).suffix.lower() in (".xapk", ".apks", ".apkm"))
        action = "install_split" if is_split else "install_single"

        self._btn_install.setEnabled(False)
        self._progress_bar.setRange(0, 0)  # Marquee

        self._worker = SideloadWorker(
            manager=self._manager,
            action=action,
            params={"path": self._selected_file_path, "flags": flags, "serial": serial},
            parent=self,
        )
        self._worker.log_emitted.connect(self._append_log)
        self._worker.operation_finished.connect(self._on_install_finished)
        self._worker.start()

    @Slot(bool, str)
    def _on_install_finished(self, success: bool, message: str) -> None:
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(100 if success else 0)
        self._update_button_states()

        if success:
            self._append_log("SUCCESS", f"Installation finished: {message}")
            QMessageBox.information(self, "Installation Complete", message)
        else:
            self._append_log("ERROR", f"Installation failed: {message}")
            QMessageBox.warning(self, "Installation Failed", message)

    # -----------------------------------------------------------------------
    # Recovery OTA Logic
    # -----------------------------------------------------------------------

    @Slot(str)
    def _on_recovery_file_selected(self, file_path: str) -> None:
        self._selected_ota_path = file_path
        self._lbl_selected_ota.setText(f"Selected: {Path(file_path).name} ({os.path.getsize(file_path) / (1024*1024):.2f} MB)")
        self._lbl_selected_ota.setStyleSheet("font-size: 12px; font-weight: 600; color: #0A84FF;")
        self._update_button_states()

    @Slot()
    def _on_reboot_recovery_clicked(self) -> None:
        serial = self._current_device.serial if self._current_device else ""
        self._append_log("INFO", "Rebooting device to recovery mode...")
        res = self._adb.reboot_recovery(serial=serial)
        if res.success:
            self._append_log("SUCCESS", "Device reboot command sent. Wait for recovery screen.")
        else:
            self._append_log("ERROR", f"Reboot failed: {res.stderr}")

    @Slot()
    def _on_sideload_ota_clicked(self) -> None:
        ota_path = getattr(self, "_selected_ota_path", "")
        if not ota_path or not os.path.isfile(ota_path):
            return

        serial = self._current_device.serial if self._current_device else ""
        self._btn_sideload_ota.setEnabled(False)
        self._progress_bar.setValue(0)

        self._worker = SideloadWorker(
            manager=self._manager,
            action="sideload_ota",
            params={"path": ota_path, "serial": serial},
            parent=self,
        )
        self._worker.progress_updated.connect(lambda pct, st: self._progress_bar.setValue(pct))
        self._worker.log_emitted.connect(self._append_log)
        self._worker.operation_finished.connect(self._on_sideload_ota_finished)
        self._worker.start()

    @Slot(bool, str)
    def _on_sideload_ota_finished(self, success: bool, message: str) -> None:
        self._update_button_states()
        if success:
            self._append_log("SUCCESS", f"OTA Sideload completed: {message}")
            QMessageBox.information(self, "Sideload Complete", message)
        else:
            self._append_log("ERROR", f"OTA Sideload failed: {message}")
            QMessageBox.warning(self, "Sideload Failed", message)

    # -----------------------------------------------------------------------
    # Installed Apps Logic
    # -----------------------------------------------------------------------

    def _load_packages(self, filter_type: str) -> None:
        self._btn_filter_3rd.setChecked(filter_type == "3rd_party")
        self._btn_filter_system.setChecked(filter_type == "system")
        self._btn_filter_disabled.setChecked(filter_type == "disabled")

        serial = self._current_device.serial if self._current_device else ""
        self._table.setRowCount(0)
        self._progress_bar.setRange(0, 0)

        self._worker = SideloadWorker(
            manager=self._manager,
            action="list_packages",
            params={"serial": serial, "filter_type": filter_type},
            parent=self,
        )
        self._worker.log_emitted.connect(self._append_log)
        self._worker.packages_loaded.connect(self._populate_package_table)
        self._worker.operation_finished.connect(lambda ok, msg: self._progress_bar.setRange(0, 100))
        self._worker.start()

    def _refresh_current_package_filter(self) -> None:
        curr = "3rd_party"
        if self._btn_filter_system.isChecked():
            curr = "system"
        elif self._btn_filter_disabled.isChecked():
            curr = "disabled"
        self._load_packages(curr)

    @Slot(list)
    def _populate_package_table(self, items: list[SideloadAppItem]) -> None:
        self._cached_package_items = items
        self._filter_package_table(self._search_input.text())

    def _filter_package_table(self, text: str) -> None:
        query = (text or "").lower().strip()
        filtered = [
            it for it in self._cached_package_items
            if not query or query in it.package_name.lower() or query in it.label.lower()
        ]

        self._table.setRowCount(len(filtered))
        for row, item in enumerate(filtered):
            name_item = QTableWidgetItem(item.package_name)
            name_item.setData(Qt.ItemDataRole.UserRole, item)
            cat_item = QTableWidgetItem(item.category.title())
            status_item = QTableWidgetItem("Enabled" if item.is_enabled else "Frozen")
            if not item.is_enabled:
                status_item.setForeground(QColor("#FF453A"))
            else:
                status_item.setForeground(QColor("#30D158"))
            path_item = QTableWidgetItem(item.path)

            self._table.setItem(row, 0, name_item)
            self._table.setItem(row, 1, cat_item)
            self._table.setItem(row, 2, status_item)
            self._table.setItem(row, 3, path_item)

    def _on_table_selection_changed(self) -> None:
        selected = self._get_selected_package()
        has_sel = selected is not None
        self._btn_pull.setEnabled(has_sel)
        self._btn_clear_data.setEnabled(has_sel)
        self._btn_force_stop.setEnabled(has_sel)
        self._btn_toggle_disable.setEnabled(has_sel)
        self._btn_uninstall.setEnabled(has_sel)

        if selected:
            if selected.is_enabled:
                self._btn_toggle_disable.setText("Disable (Freeze)")
                self._btn_toggle_disable.setIcon(get_icon("lock", 12))
            else:
                self._btn_toggle_disable.setText("Enable (Unfreeze)")
                self._btn_toggle_disable.setIcon(get_icon("unlock", 12))

    def _get_selected_package(self) -> Optional[SideloadAppItem]:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _execute_pkg_action(self, action: str) -> None:
        pkg = self._get_selected_package()
        if not pkg:
            return

        serial = self._current_device.serial if self._current_device else ""
        dest_dir = None
        if action == "pull":
            dest_dir = QFileDialog.getExistingDirectory(self, "Select Save Directory for Extracted APK")
            if not dest_dir:
                return

        if action == "uninstall":
            reply = QMessageBox.question(
                self,
                "Confirm Package Uninstall",
                f"Are you sure you want to uninstall '{pkg.package_name}'?\nThis will remove application binaries and data.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._worker = SideloadWorker(
            manager=self._manager,
            action="manage_package",
            params={
                "package_name": pkg.package_name,
                "pkg_action": action,
                "serial": serial,
                "dest_dir": dest_dir,
            },
            parent=self,
        )
        self._worker.log_emitted.connect(self._append_log)
        self._worker.operation_finished.connect(self._on_pkg_action_finished)
        self._worker.start()

    def _toggle_disable_selected(self) -> None:
        pkg = self._get_selected_package()
        if not pkg:
            return
        act = "disable" if pkg.is_enabled else "enable"
        self._execute_pkg_action(act)

    @Slot(bool, str)
    def _on_pkg_action_finished(self, success: bool, message: str) -> None:
        if success:
            self._append_log("SUCCESS", message)
            QMessageBox.information(self, "Operation Successful", message)
            self._refresh_current_package_filter()
        else:
            self._append_log("ERROR", message)
            QMessageBox.warning(self, "Operation Failed", message)

    # -----------------------------------------------------------------------
    # Logging & Theme Support
    # -----------------------------------------------------------------------

    @Slot(str, str)
    def _append_log(self, level: str, msg: str) -> None:
        self._log_terminal.appendPlainText(f"[{level.upper()}] {msg}")
        self._log_terminal.verticalScrollBar().setValue(
            self._log_terminal.verticalScrollBar().maximum()
        )

    def apply_theme(self, theme: str) -> None:
        """Seamless Dark/Light theme switching."""
        self._current_theme = theme.lower()
        if hasattr(self, "_dropzone"):
            self._dropzone._apply_normal_style(self._current_theme)
        if hasattr(self, "_dropzone_recovery"):
            self._dropzone_recovery._apply_normal_style(self._current_theme)

        if self._current_theme == "light":
            self._meta_card.setStyleSheet("""
                QFrame {
                    background-color: #ECEFF4;
                    border: 1px solid #CBD1DC;
                    border-radius: 14px;
                    padding: 10px;
                }
            """)
            self._meta_title_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #1C2024;")
            self._log_terminal.setStyleSheet("""
                QPlainTextEdit {
                    font-family: Consolas, 'SF Mono', monospace;
                    font-size: 11px;
                    background-color: #F8FAFC;
                    color: #0F172A;
                    border: 1px solid #CBD1DC;
                    border-radius: 8px;
                    padding: 6px;
                }
            """)
        else:
            self._meta_card.setStyleSheet("""
                QFrame {
                    background-color: #161D28;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 14px;
                    padding: 10px;
                }
            """)
            self._meta_title_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #FFFFFF;")
            self._log_terminal.setStyleSheet("""
                QPlainTextEdit {
                    font-family: Consolas, 'SF Mono', monospace;
                    font-size: 11px;
                    background-color: #0D1117;
                    color: #58A6FF;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 8px;
                    padding: 6px;
                }
            """)
