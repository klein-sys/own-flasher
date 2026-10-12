"""
FlashDock — Logs, Telemetry & Interactive Troubleshooting Center (Phase 15).

Provides a comprehensive diagnostic hub:
1. Real-time application logs viewer with file switcher, level filtering, and search.
2. Device logcat & dmesg kernel log capture and export.
3. Interactive guided troubleshooting wizard with one-click recovery actions.
4. Offline partition architecture knowledge base and root solutions cheat sheet.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from flashdock.constants import LOGS_DIR
from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.core.troubleshooter import (
    TROUBLESHOOTING_CATALOG,
    TroubleshooterManager,
    TroubleshootingItem,
)
from flashdock.logger import get_log_file_path, get_logger, mask_serials
from flashdock.ui.icon_assets import create_icon_label, get_icon
from flashdock.ui.widgets.selftest_dialog import SelfTestDialog
from flashdock.tools.adb import ADB

log = get_logger(__name__)


class LogsHelpScreen(QWidget):
    """Logs, Telemetry & Troubleshooting Center screen."""

    navigate_to_page = Signal(int)

    def __init__(
        self,
        device_mgr: DeviceManager,
        adb: ADB,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._device_mgr = device_mgr
        self._adb = adb
        self._troubleshooter = TroubleshooterManager(adb=adb)
        self._current_device: Optional[DeviceInfo] = None
        self._raw_log_lines: list[str] = []

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(14)

        # -------------------------------------------------------------
        # Header Row
        # -------------------------------------------------------------
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_h = QHBoxLayout()
        title_h.setSpacing(8)
        title_h.addWidget(create_icon_label("logs_help", 22))
        title = QLabel("Logs, Telemetry & Troubleshooting Center")
        title.setProperty("cssClass", "heading")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        title_h.addWidget(title)
        title_h.addStretch(1)
        title_box.addLayout(title_h)

        self._subtitle = QLabel(
            "Inspect application telemetry, stream device logcat, and solve connection or boot issues."
        )
        self._subtitle.setStyleSheet("color: #8E8E93; font-size: 12px;")
        title_box.addWidget(self._subtitle)
        header_row.addLayout(title_box, 1)

        # Quick actions in header
        open_logs_btn = QPushButton("Open Logs Folder")
        open_logs_btn.setIcon(get_icon("folder", 14))
        open_logs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_logs_btn.setToolTip("Open data/logs in Windows Explorer")
        open_logs_btn.clicked.connect(self._open_logs_folder)
        header_row.addWidget(open_logs_btn)

        restart_adb_btn = QPushButton("Restart ADB")
        restart_adb_btn.setIcon(get_icon("refresh", 14))
        restart_adb_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        restart_adb_btn.setStyleSheet(
            "QPushButton { background-color: rgba(10, 132, 255, 0.12); color: #0A84FF; "
            "border: 1px solid rgba(10, 132, 255, 0.3); border-radius: 8px; padding: 6px 14px; font-weight: 600; } "
            "QPushButton:hover { background-color: rgba(10, 132, 255, 0.22); }"
        )
        restart_adb_btn.clicked.connect(self._restart_adb_server)
        header_row.addWidget(restart_adb_btn)

        layout.addLayout(header_row)

        # -------------------------------------------------------------
        # Tabs Container
        # -------------------------------------------------------------
        self._tabs = QTabWidget()

        self._tab_app_logs = QWidget()
        self._tab_logcat = QWidget()
        self._tab_troubleshoot = QWidget()
        self._tab_knowledge = QWidget()

        self._setup_app_logs_tab()
        self._setup_logcat_tab()
        self._setup_troubleshoot_tab()
        self._setup_knowledge_tab()

        self._tabs.addTab(self._tab_app_logs, get_icon("logs_help", 16), "FlashDock Application Logs")
        self._tabs.addTab(self._tab_logcat, get_icon("phone", 16), "Device Logcat & Kernel dmesg")
        self._tabs.addTab(self._tab_troubleshoot, get_icon("tools", 16), "Guided Interactive Troubleshooting")
        self._tabs.addTab(self._tab_knowledge, get_icon("book", 16), "Partition & Architecture Guide")

        layout.addWidget(self._tabs, 1)

    # -----------------------------------------------------------------
    # Tab 1: FlashDock Application Logs
    # -----------------------------------------------------------------

    def _setup_app_logs_tab(self) -> None:
        layout = QVBoxLayout(self._tab_app_logs)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        f_lbl = QLabel("File:")
        f_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #8E8E93;")
        toolbar.addWidget(f_lbl)

        self._file_combo = QComboBox()
        self._file_combo.setMinimumHeight(30)
        self._file_combo.setMinimumWidth(180)
        self._file_combo.currentIndexChanged.connect(self._on_log_file_selected)
        toolbar.addWidget(self._file_combo)

        reload_btn = QPushButton("")
        reload_btn.setIcon(get_icon("refresh", 14))
        reload_btn.setToolTip("Reload log files list and content")
        reload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reload_btn.clicked.connect(self._refresh_log_files_list)
        toolbar.addWidget(reload_btn)

        toolbar.addSpacing(10)

        lvl_lbl = QLabel("Level:")
        lvl_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #8E8E93;")
        toolbar.addWidget(lvl_lbl)

        self._level_combo = QComboBox()
        self._level_combo.addItems(["All Levels", "INFO", "WARNING", "ERROR", "DEBUG"])
        self._level_combo.setMinimumHeight(30)
        self._level_combo.currentIndexChanged.connect(self._apply_log_filters)
        toolbar.addWidget(self._level_combo)

        toolbar.addSpacing(10)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Filter logs by keyword...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setMinimumHeight(30)
        self._search_input.textChanged.connect(self._apply_log_filters)
        toolbar.addWidget(self._search_input, 1)

        self._match_badge = QLabel("0 lines")
        self._match_badge.setStyleSheet("font-size: 11px; color: #8E8E93; font-weight: 500;")
        toolbar.addWidget(self._match_badge)

        self._autoscroll_cb = QCheckBox("Auto-scroll")
        self._autoscroll_cb.setChecked(True)
        toolbar.addWidget(self._autoscroll_cb)

        layout.addLayout(toolbar)

        # Log text viewer
        self._log_viewer = QPlainTextEdit()
        self._log_viewer.setReadOnly(True)
        self._log_viewer.setFont(QFont("Consolas", 10))
        self._log_viewer.setStyleSheet(
            "QPlainTextEdit { background-color: #121214; color: #E5E5EA; "
            "border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 10px; }"
        )
        layout.addWidget(self._log_viewer, 1)

        # Bottom actions
        bot_row = QHBoxLayout()
        bot_row.setSpacing(10)

        export_btn = QPushButton("Export Log (Mask Serials)")
        export_btn.setIcon(get_icon("save", 14))
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setToolTip("Export current log file with device serials scrubbed for sharing")
        export_btn.clicked.connect(self._export_log_file)
        bot_row.addWidget(export_btn)

        copy_btn = QPushButton("Copy All Visible")
        copy_btn.setIcon(get_icon("copy", 14))
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(self._copy_visible_logs)
        bot_row.addWidget(copy_btn)

        clear_btn = QPushButton("Clear Viewer")
        clear_btn.setIcon(get_icon("trash", 14))
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._log_viewer.clear)
        bot_row.addWidget(clear_btn)

        bot_row.addStretch(1)

        self._log_status_lbl = QLabel("Loaded.")
        self._log_status_lbl.setStyleSheet("font-size: 11px; color: #8E8E93;")
        bot_row.addWidget(self._log_status_lbl)

        layout.addLayout(bot_row)

        # Populate files
        self._refresh_log_files_list()

    # -----------------------------------------------------------------
    # Tab 2: Device Logcat & Kernel dmesg
    # -----------------------------------------------------------------

    def _setup_logcat_tab(self) -> None:
        layout = QVBoxLayout(self._tab_logcat)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Control Row
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(10)

        b_lbl = QLabel("Buffer:")
        b_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #8E8E93;")
        ctrl_row.addWidget(b_lbl)

        self._logcat_buffer_combo = QComboBox()
        self._logcat_buffer_combo.addItems(["main", "system", "crash", "events", "kernel (dmesg)"])
        self._logcat_buffer_combo.setMinimumHeight(30)
        ctrl_row.addWidget(self._logcat_buffer_combo)

        ctrl_row.addSpacing(6)

        l_lbl = QLabel("Lines:")
        l_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #8E8E93;")
        ctrl_row.addWidget(l_lbl)

        self._logcat_lines_spin = QSpinBox()
        self._logcat_lines_spin.setRange(50, 5000)
        self._logcat_lines_spin.setValue(300)
        self._logcat_lines_spin.setSingleStep(100)
        self._logcat_lines_spin.setMinimumHeight(30)
        ctrl_row.addWidget(self._logcat_lines_spin)

        ctrl_row.addSpacing(6)

        self._logcat_filter_input = QLineEdit()
        self._logcat_filter_input.setPlaceholderText("Filter tag or regex (e.g. AndroidRuntime:E, *:S, FATAL)...")
        self._logcat_filter_input.setClearButtonEnabled(True)
        self._logcat_filter_input.setMinimumHeight(30)
        ctrl_row.addWidget(self._logcat_filter_input, 1)

        self._capture_logcat_btn = QPushButton("Capture Dump")
        self._capture_logcat_btn.setIcon(get_icon("play", 14))
        self._capture_logcat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._capture_logcat_btn.setStyleSheet(
            "QPushButton { background-color: #0A84FF; color: #FFFFFF; font-weight: 600; "
            "border-radius: 6px; padding: 6px 14px; min-height: 20px; } "
            "QPushButton:hover { background-color: #0071E3; }"
        )
        self._capture_logcat_btn.clicked.connect(self._run_logcat_capture)
        ctrl_row.addWidget(self._capture_logcat_btn)

        clear_buf_btn = QPushButton("Clear Buffer")
        clear_buf_btn.setIcon(get_icon("trash", 14))
        clear_buf_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_buf_btn.setToolTip("Run adb logcat -c to empty device circular buffer")
        clear_buf_btn.clicked.connect(self._clear_device_logcat)
        ctrl_row.addWidget(clear_buf_btn)

        layout.addLayout(ctrl_row)

        # Logcat display
        self._logcat_viewer = QPlainTextEdit()
        self._logcat_viewer.setReadOnly(True)
        self._logcat_viewer.setFont(QFont("Consolas", 10))
        self._logcat_viewer.setStyleSheet(
            "QPlainTextEdit { background-color: #121214; color: #30D158; "
            "border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 10px; }"
        )
        layout.addWidget(self._logcat_viewer, 1)

        # Logcat bottom toolbar
        lc_bot = QHBoxLayout()
        lc_bot.setSpacing(10)

        save_lc_btn = QPushButton("Save Logcat Dump")
        save_lc_btn.setIcon(get_icon("save", 14))
        save_lc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_lc_btn.clicked.connect(self._save_logcat_file)
        lc_bot.addWidget(save_lc_btn)

        copy_lc_btn = QPushButton("Copy to Clipboard")
        copy_lc_btn.setIcon(get_icon("copy", 14))
        copy_lc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_lc_btn.clicked.connect(self._copy_logcat)
        lc_bot.addWidget(copy_lc_btn)

        lc_bot.addStretch(1)

        self._logcat_status_lbl = QLabel("Connect a device in System mode and click 'Capture Dump'.")
        self._logcat_status_lbl.setStyleSheet("font-size: 11px; color: #8E8E93;")
        lc_bot.addWidget(self._logcat_status_lbl)

        layout.addLayout(lc_bot)

    # -----------------------------------------------------------------
    # Tab 3: Guided Interactive Troubleshooting
    # -----------------------------------------------------------------

    def _setup_troubleshoot_tab(self) -> None:
        layout = QVBoxLayout(self._tab_troubleshoot)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Phase 16 Self-Test Diagnostics Banner Card
        st_card = QFrame()
        st_card.setStyleSheet(
            "QFrame { background-color: rgba(10, 132, 255, 0.08); border: 1px solid rgba(10, 132, 255, 0.25); "
            "border-radius: 10px; padding: 12px; }"
        )
        st_lay = QHBoxLayout(st_card)
        st_lay.setContentsMargins(8, 4, 8, 4)
        st_lay.setSpacing(12)

        st_icon = create_icon_label("flash", 22)
        st_lay.addWidget(st_icon)

        st_text_col = QVBoxLayout()
        st_text_col.setSpacing(2)
        st_title = QLabel("System Environment & Toolchain Self-Test")
        st_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #0A84FF;")
        st_desc = QLabel("Automated verification of ADB/Fastboot binaries, user data permissions, and network readiness.")
        st_desc.setStyleSheet("font-size: 11px; color: #8E8E93;")
        st_text_col.addWidget(st_title)
        st_text_col.addWidget(st_desc)
        st_lay.addLayout(st_text_col, 1)

        run_st_btn = QPushButton("Run Self-Test")
        run_st_btn.setIcon(get_icon("play", 14))
        run_st_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        run_st_btn.setStyleSheet(
            "QPushButton { background-color: #0A84FF; color: #FFFFFF; font-weight: 600; "
            "border-radius: 6px; padding: 6px 14px; font-size: 12px; } "
            "QPushButton:hover { background-color: #0071E3; }"
        )
        run_st_btn.clicked.connect(self._open_selftest)
        st_lay.addWidget(run_st_btn)

        layout.addWidget(st_card)

        desc = QLabel(
            "Select a common issue below for step-by-step solutions and 1-click automated rescue actions."
        )
        desc.setStyleSheet("color: #8E8E93; font-size: 12px;")
        layout.addWidget(desc)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(12)

        for item in TROUBLESHOOTING_CATALOG:
            box = self._create_troubleshoot_card(item)
            c_layout.addWidget(box)

        c_layout.addStretch(1)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

    def _create_troubleshoot_card(self, item: TroubleshootingItem) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background-color: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.08); "
            "border-radius: 10px; padding: 14px; }"
        )
        lay = QVBoxLayout(frame)
        lay.setSpacing(8)

        # Header with icon and title
        h_row = QHBoxLayout()
        h_row.setSpacing(8)

        icon_map = {
            "device_not_detected": "usb",
            "fastboot_waiting": "flash",
            "bootloop_rescue": "unbrick",
            "play_integrity_fail": "integrity",
            "xiaomi_wait_time": "tools",
            "samsung_knox_trip": "lock",
        }
        card_icon = icon_map.get(item.id, "tools")
        h_row.addWidget(create_icon_label(card_icon, 18))

        t_lbl = QLabel(item.title)
        t_lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #FFFFFF;")
        h_row.addWidget(t_lbl, 1)

        # Quick action button if available
        if item.quick_action_id:
            clean_label = item.quick_action_label.strip()
            act_btn = QPushButton(clean_label)
            btn_icon_name = "refresh" if "restart" in item.quick_action_id else ("tools" if "device_manager" in item.quick_action_id else ("unbrick" if "unbrick" in item.quick_action_id else "integrity"))
            act_btn.setIcon(get_icon(btn_icon_name, 14))
            act_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            act_btn.setStyleSheet(
                "QPushButton { background-color: rgba(10, 132, 255, 0.15); color: #0A84FF; "
                "border: 1px solid rgba(10, 132, 255, 0.3); border-radius: 6px; padding: 5px 12px; font-weight: 600; font-size: 12px; } "
                "QPushButton:hover { background-color: rgba(10, 132, 255, 0.25); }"
            )
            act_btn.clicked.connect(lambda _, it=item: self._on_troubleshoot_action(it))
            h_row.addWidget(act_btn)

        lay.addLayout(h_row)

        # Symptom
        s_lbl = QLabel(f"<b>Symptom:</b> {item.symptom}")
        s_lbl.setStyleSheet("font-size: 12px; color: #E5E5EA;")
        s_lbl.setWordWrap(True)
        lay.addWidget(s_lbl)

        # Causes
        c_text = "<b>Likely Causes:</b><br>• " + "<br>• ".join(item.causes)
        c_lbl = QLabel(c_text)
        c_lbl.setStyleSheet("font-size: 11px; color: #8E8E93; line-height: 1.3;")
        c_lbl.setWordWrap(True)
        lay.addWidget(c_lbl)

        # Steps
        steps_text = "<b>Recommended Steps to Fix:</b><br>" + "<br>".join(item.steps)
        st_lbl = QLabel(steps_text)
        st_lbl.setStyleSheet("font-size: 12px; color: #30D158; line-height: 1.4;")
        st_lbl.setWordWrap(True)
        lay.addWidget(st_lbl)

        return frame

    # -----------------------------------------------------------------
    # Tab 4: Knowledge Base & Partition Reference
    # -----------------------------------------------------------------

    def _setup_knowledge_tab(self) -> None:
        layout = QVBoxLayout(self._tab_knowledge)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(14)

        topics = [
            (
                "folder",
                "Critical Android Partition Layout & Roles",
                "• <b>boot.img</b>: Contains the Linux kernel and root ramdisk (on Android 12 and older).\n"
                "• <b>init_boot.img</b>: Introduced in Android 13 (GKI 2.0). Contains the genuine init ramdisk. Magisk and KernelSU patch THIS partition on modern devices.\n"
                "• <b>vbmeta.img</b>: Android Verified Boot (AVB 2.0) hash tree and cryptographic signing. Corrupting this causes immediate bootloops.\n"
                "• <b>super.img</b>: Dynamic partition container hosting system, system_ext, vendor, product, and odm sub-partitions.\n"
                "• <b>persist / efs</b>: Factory calibration, Wi-Fi MAC address, Bluetooth keys, and cellular IMEI data. NEVER wipe this partition!\n"
                "• <b>dtbo.img</b>: Device Tree Blob Overlay, defines hardware pin configurations and peripheral timing.",
            ),
            (
                "refresh",
                "A/B Seamless Partition Scheme Explained",
                "• Devices with A/B partitioning feature two copies of boot partitions (e.g., boot_a and boot_b, system_a and system_b).\n"
                "• During an OTA update, the inactive slot is flashed in the background. On reboot, the device attempts to boot from the updated slot.\n"
                "• If boot fails 7 times consecutively, the hardware automatically rolls back to the previous working slot!\n"
                "• In Fastboot, you can manually switch active slots via: <code>fastboot --set-active=a</code> or <code>b</code>.",
            ),
            (
                "shield",
                "Root Method Architecture Comparison",
                "• <b>Magisk</b>: Systemless root patching boot.img ramdisk. Operates at init stage. Features Zygisk in-memory hooking and module ecosystem.\n"
                "• <b>KernelSU</b>: Kernel-level root residing directly inside Linux kernel space. Zero root footprint in userspace. Highly stealthy against banking apps.\n"
                "• <b>APatch</b>: KernelPatch-based root combining KernelSU's kernel space hook with SuperKey access control. Works on non-GKI legacy kernels.",
            ),
            (
                "flash",
                "Fastboot vs FastbootD (Userspace Fastboot)",
                "• <b>Bootloader Fastboot</b>: Hosted by the motherboard bootloader (abl/xbl). Used for unlocking bootloader and flashing boot, init_boot, recovery, and vbmeta.\n"
                "• <b>FastbootD</b>: Hosted in userspace recovery ramdisk. REQUIRED for flashing dynamic sub-partitions inside super (system, vendor, product).",
            ),
        ]

        for icon_key, title, body in topics:
            box = QFrame()
            box.setStyleSheet(
                "background-color: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.08); "
                "border-radius: 10px; padding: 14px;"
            )
            b_layout = QVBoxLayout(box)
            b_layout.setSpacing(6)

            h_box = QHBoxLayout()
            h_box.setSpacing(8)
            h_box.addWidget(create_icon_label(icon_key, 16))
            t = QLabel(title)
            t.setStyleSheet("font-size: 13px; font-weight: 700; color: #FFFFFF;")
            h_box.addWidget(t, 1)
            b_layout.addLayout(h_box)

            b = QLabel(body.replace("\n", "<br>"))
            b.setStyleSheet("font-size: 12px; color: #8E8E93; line-height: 1.4;")
            b.setWordWrap(True)
            b_layout.addWidget(b)

            c_layout.addWidget(box)

        c_layout.addStretch(1)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

    # -----------------------------------------------------------------
    # Logic & Event Handlers
    # -----------------------------------------------------------------

    def load_for_device(self, device: Optional[DeviceInfo]) -> None:
        """Called by MainWindow when device state changes or screen is opened."""
        self._current_device = device
        if device and device.mode != "not_connected":
            self._subtitle.setText(f"Active Device: {device.model} ({device.serial}) · Mode: {device.mode.upper()}")
            self._logcat_status_lbl.setText(f"Targeting {device.model} ({device.serial})")
        else:
            self._subtitle.setText("No device connected. FlashDock application logs are active.")
            self._logcat_status_lbl.setText("No device connected. Connect phone to stream logcat.")

    def _refresh_log_files_list(self) -> None:
        """Find all flashdock_*.log files in LOGS_DIR and update combo."""
        files = self._troubleshooter.list_log_files()
        self._file_combo.blockSignals(True)
        self._file_combo.clear()

        cur_active = get_log_file_path()
        active_idx = 0

        for idx, f in enumerate(files):
            self._file_combo.addItem(f.name, str(f))
            if cur_active and f.resolve() == cur_active.resolve():
                active_idx = idx

        if self._file_combo.count() > 0:
            self._file_combo.setCurrentIndex(active_idx)
            self._file_combo.blockSignals(False)
            self._on_log_file_selected(active_idx)
        else:
            self._file_combo.blockSignals(False)
            self._log_viewer.setPlainText("No log files found in data/logs.")

    def _on_log_file_selected(self, index: int) -> None:
        """Load selected log file content into memory and render."""
        if index < 0 or index >= self._file_combo.count():
            return

        f_path = Path(self._file_combo.currentData())
        if not f_path.exists():
            self._log_viewer.setPlainText(f"File not found: {f_path}")
            return

        try:
            content = f_path.read_text(encoding="utf-8", errors="replace")
            self._raw_log_lines = content.splitlines()
            self._apply_log_filters()
            self._log_status_lbl.setText(f"Loaded {len(self._raw_log_lines)} lines from {f_path.name}")
        except Exception as exc:
            self._log_viewer.setPlainText(f"Error reading file:\n{exc}")

    def _apply_log_filters(self) -> None:
        """Filter log lines by selected level and keyword query."""
        level_filter = self._level_combo.currentText().upper()
        query = self._search_input.text().strip().lower()

        filtered: list[str] = []
        for line in self._raw_log_lines:
            # Level check
            if level_filter != "ALL LEVELS":
                if f"| {level_filter}" not in line:
                    continue

            # Query check
            if query and query not in line.lower():
                continue

            filtered.append(line)

        # Update text viewer
        self._log_viewer.setPlainText("\n".join(filtered))
        self._match_badge.setText(f"{len(filtered)} / {len(self._raw_log_lines)} lines")

        if self._autoscroll_cb.isChecked():
            cursor = self._log_viewer.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self._log_viewer.setTextCursor(cursor)

    def _export_log_file(self) -> None:
        """Export current log with serial numbers masked for privacy."""
        content = self._log_viewer.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "Empty Log", "No log lines to export.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Masked Log",
            "flashdock_debug_log.txt",
            "Text Files (*.txt);;All Files (*.*)",
        )
        if not path:
            return

        masked = mask_serials(content)
        try:
            Path(path).write_text(masked, encoding="utf-8")
            QMessageBox.information(
                self,
                "Log Exported",
                f"Exported log successfully to:\n{path}\n\nAll device serial numbers were masked with [SERIAL].",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", f"Failed to save log:\n{exc}")

    def _copy_visible_logs(self) -> None:
        """Copy all visible logs to system clipboard."""
        self._log_viewer.selectAll()
        self._log_viewer.copy()
        cursor = self._log_viewer.textCursor()
        cursor.clearSelection()
        self._log_viewer.setTextCursor(cursor)
        self._log_status_lbl.setText("Copied visible log lines to clipboard.")

    def _run_logcat_capture(self) -> None:
        """Capture tail lines of logcat from current device."""
        if not self._current_device or self._current_device.mode == "not_connected":
            QMessageBox.warning(self, "No Device", "Please connect an Android device in System mode.")
            return

        buf = self._logcat_buffer_combo.currentText()
        lines = self._logcat_lines_spin.value()
        filt = self._logcat_filter_input.text()

        self._logcat_status_lbl.setText("Capturing logcat from device...")
        self._capture_logcat_btn.setEnabled(False)

        def _do_capture() -> None:
            if "kernel" in buf:
                ok, text = self._troubleshooter.capture_dmesg(self._current_device.serial)
            else:
                ok, text = self._troubleshooter.capture_logcat(
                    serial=self._current_device.serial,
                    buffer_name=buf,
                    lines=lines,
                    filter_spec=filt,
                )
            self._capture_logcat_btn.setEnabled(True)
            if ok:
                self._logcat_viewer.setPlainText(text)
                self._logcat_status_lbl.setText(f"Captured {len(text.splitlines())} lines from buffer '{buf}'.")
            else:
                self._logcat_viewer.setPlainText(f"Logcat capture failed:\n{text}")
                self._logcat_status_lbl.setText("Logcat capture failed.")

        QTimer.singleShot(50, _do_capture)

    def _clear_device_logcat(self) -> None:
        """Clear device logcat circular buffer via logcat -c."""
        if not self._current_device or self._current_device.mode == "not_connected":
            QMessageBox.warning(self, "No Device", "Please connect an Android device.")
            return

        ok, msg = self._troubleshooter.clear_device_logcat(self._current_device.serial)
        if ok:
            self._logcat_viewer.clear()
            self._logcat_status_lbl.setText("Device logcat circular buffer cleared.")
        else:
            QMessageBox.warning(self, "Clear Failed", msg)

    def _save_logcat_file(self) -> None:
        """Save captured logcat text to disk."""
        text = self._logcat_viewer.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Empty Logcat", "No logcat output to save.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Logcat Dump",
            "device_logcat.txt",
            "Text Files (*.txt);;All Files (*.*)",
        )
        if not path:
            return

        try:
            Path(path).write_text(text, encoding="utf-8")
            QMessageBox.information(self, "Saved", f"Logcat dump saved to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", f"Failed to save file:\n{exc}")

    def _copy_logcat(self) -> None:
        """Copy logcat text to clipboard."""
        self._logcat_viewer.selectAll()
        self._logcat_viewer.copy()
        cursor = self._logcat_viewer.textCursor()
        cursor.clearSelection()
        self._logcat_viewer.setTextCursor(cursor)
        self._logcat_status_lbl.setText("Copied logcat dump to clipboard.")

    def _open_logs_folder(self) -> None:
        """Open logs directory."""
        ok, msg = self._troubleshooter.open_logs_folder()
        if not ok:
            QMessageBox.warning(self, "Folder Error", msg)

    def _restart_adb_server(self) -> None:
        """Restart ADB server daemon cleanly."""
        ok, msg = self._troubleshooter.restart_adb()
        if ok:
            QMessageBox.information(self, "ADB Restarted", msg)
        else:
            QMessageBox.warning(self, "ADB Restart Error", msg)

    def _on_troubleshoot_action(self, item: TroubleshootingItem) -> None:
        """Handle 1-click rescue button on troubleshooting cards."""
        act_id = item.quick_action_id

        if act_id == "restart_adb":
            self._restart_adb_server()
        elif act_id == "open_device_manager":
            ok, msg = self._troubleshooter.open_device_manager()
            if not ok:
                QMessageBox.warning(self, "Error", msg)
        elif item.navigation_target is not None:
            # Emit navigation signal to switch page in MainWindow
            self.navigate_to_page.emit(item.navigation_target)

    def _open_selftest(self) -> None:
        """Launch the system health and toolchain self-test modal dialog."""
        dlg = SelfTestDialog(self)
        dlg.exec()
