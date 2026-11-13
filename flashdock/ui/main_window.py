"""
FlashDock — Main application window.

Assembles four glass workflow sheets, a unified device island,
sidebar controls, and the existing device-service screens.
"""

from __future__ import annotations

import logging
from functools import partial
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTimer, Qt, Signal, Slot
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from flashdock import __app_name__, __version__
from flashdock.config import Config
from flashdock.constants import TOOLS_DIR
from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.core.device_state_sync import DeviceStateBroadcaster
from flashdock.core.network import NetworkMonitor
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot
from flashdock.tools.runner import is_flash_locked
from flashdock.tools.scrcpy import ScrcpyManager
from flashdock.ui.screens.checklist_screen import ChecklistScreen
from flashdock.ui.screens.unlock_screen import UnlockScreen
from flashdock.ui.screens.backup_screen import BackupScreen
from flashdock.ui.screens.root_screen import RootScreen
from flashdock.ui.screens.modules_screen import ModulesScreen
from flashdock.ui.screens.return_stock_screen import ReturnStockScreen
from flashdock.ui.screens.flash_rom_screen import FlashRomScreen
from flashdock.ui.screens.diagnostics_screen import DiagnosticsScreen
from flashdock.ui.screens.mtk_unisoc_screen import MtkUnisocScreen
from flashdock.ui.screens.downloads_screen import DownloadsScreen
from flashdock.ui.screens.unbrick_screen import UnbrickScreen
from flashdock.ui.screens.integrity_screen import IntegrityScreen
from flashdock.ui.screens.logs_help_screen import LogsHelpScreen
from flashdock.ui.screens.sideload_screen import SideloadScreen
from flashdock.ui.styles import get_stylesheet
from flashdock.ui.widgets.device_card import DeviceCard
from flashdock.ui.widgets.device_hud import LiveDeviceHud
from flashdock.ui.widgets.dynamic_island import ObsidianDynamicIslandBar
from flashdock.ui.widgets.liquid_glass_widget import (
    LiquidGlassActionRow,
    LiquidGlassCanvas,
    LiquidGlassSheet,
    enable_windows_acrylic_blur,
)
from flashdock.ui.widgets.device_selector import DeviceSelector
from flashdock.ui.widgets.header_inspector_dialog import PartitionHeaderInspectorDialog
from flashdock.ui.widgets.key_guide_dialog import HardwareKeyGuideDialog
from flashdock.ui.widgets.phone_panel import PhoneControlPanel
from flashdock.ui.widgets.reboot_switchboard import RebootSwitchboardDialog
from flashdock.ui.widgets.scrcpy_dialog import ScrcpyDialog
from flashdock.ui.widgets.selftest_dialog import SelfTestDialog
from flashdock.ui.widgets.settings_dialog import SettingsDialog
from flashdock.ui.widgets.setup_wizard_dialog import SetupWizardDialog
from flashdock.ui.widgets.side_terminal import SideTerminalHandler, SideTerminalWidget
from flashdock.ui.widgets.status_bar import StatusBarWidget
from flashdock.ui.widgets.workflow_guide import WorkflowGuideDialog
from flashdock.workers.device_monitor import DeviceMonitorWorker
from flashdock.workers.flash_engine import FlashEngineWorker
from flashdock.core.diagnostics_engine import DiagnosticsEngine
from flashdock.ui.icon_assets import create_icon_label, get_icon

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Main action definitions (id, icon_name, label, description, category, tags)
# ---------------------------------------------------------------------------
MAIN_ACTIONS = [
    ("check_phone",   "search",       "Check my phone",        "Detect device & show full hardware specs", "Device", ["check", "detect", "specs", "usb", "serial", "model", "phone", "state", "mode", "info"]),
    ("checklist",     "checklist",    "Safety Checklist",      "Pre-flash verification & safety prerequisites", "Rescue", ["checklist", "prep", "safe", "battery", "usb debugging", "prerequisites", "safety"]),
    ("unlock_bl",     "unlock",       "Unlock Bootloader",     "Brand-aware bootloader unlock wizard", "Flashing", ["unlock", "bootloader", "fastboot", "oem", "xiaomi", "pixel", "samsung", "motorola", "bl"]),
    ("root",          "root",         "Root my phone",          "Magisk, KernelSU & APatch automated rooting", "Root", ["root", "magisk", "kernelsu", "apatch", "su", "superuser", "boot.img", "patch"]),
    ("flash_rom",     "flash",        "Flash ROM / GSI",       "Flash custom ROMs, GSIs, or TWRP/OrangeFox", "Flashing", ["flash", "rom", "gsi", "custom", "lineage", "twrp", "recovery", "fastboot", "payload", "zip"]),
    ("modules",       "modules",      "Manage Modules",        "Install, manage, and toggle root modules", "Root", ["module", "modules", "magisk", "lsposed", "zygisk", "zip", "install", "active"]),
    ("diagnostics",   "diagnostics",  "Diagnostics & Tweaks",  "Debloat apps, battery health, system tweaks", "Device", ["diagnostics", "debloat", "battery", "tweaks", "apps", "performance", "system", "speed"]),
    ("sideload",      "box",          "Sideload & App Manager", "Install APKs, split XAPKs, bypass Android 14 restrictions, & recovery sideload", "Device", ["sideload", "apk", "xapk", "apks", "install", "bundle", "apps", "debloat", "ota", "package", "permissions"]),
    ("integrity",     "integrity",    "Fix Play Integrity",     "Play Integrity diagnosis & fingerprint fixer", "Root", ["integrity", "play integrity", "safetynet", "cts", "banking", "fingerprint", "fix"]),
    ("backup",        "backup",       "Backup / Restore",       "Partition dumps, ADB backups & restore manager", "Rescue", ["backup", "restore", "dump", "partitions", "adb backup", "twrp", "images", "extract"]),
    ("unbrick",       "unbrick",      "Fix bricked phone",      "Emergency rescue: bootloop killer, slot rollback", "Rescue", ["unbrick", "bootloop", "brick", "rescue", "edl", "fix bootloop", "safe mode", "slot", "vbmeta", "stuck"]),
    ("return_stock",  "return_stock", "Return to Stock",        "Remove root, relock & reflash stock firmware", "Flashing", ["stock", "return", "relock", "unroot", "factory", "oem", "revert", "clean"]),
    ("mtk_unisoc",    "mtk_unisoc",   "MTK / Unisoc mode",     "MediaTek BROM, scatter files & PAC flashing", "Flashing", ["mtk", "mediatek", "unisoc", "brom", "scatter", "pac", "bflash", "preloader"]),
    ("scrcpy",        "scrcpy",       "Screen Mirror (scrcpy)", "Ultra-low latency screen mirror, touch control & audio forwarding", "Device", ["scrcpy", "mirror", "screen", "display", "remote", "touch", "record", "audio"]),
    ("downloads",     "downloads",    "Downloads & Tools",     "Platform-tools, OEM drivers & firmware repos", "Device", ["downloads", "drivers", "platform-tools", "adb", "fastboot", "usb", "firmware", "gsi"]),
    ("logs_help",     "logs_help",    "Logs & Help",            "View telemetry logs, guides & troubleshooting", "Device", ["logs", "help", "guide", "troubleshooting", "terminal", "support", "docs"]),
]

WORKFLOWS = (
    ("Inspect", "01. Inspect & Backup", ("check_phone", "checklist", "backup", "diagnostics")),
    ("Daily", "02. ADB & Daily Apps", ("sideload", "scrcpy", "downloads", "logs_help")),
    ("Root", "03. Root & Integrity", ("root", "modules", "integrity", "unlock_bl")),
    ("Flash", "04. Flash & Rescue", ("flash_rom", "unbrick", "mtk_unisoc", "return_stock")),
)

# Page indices in the stacked widget
PAGE_HOME = 0
PAGE_DEVICE_CARD = 1
PAGE_CHECKLIST = 2
PAGE_UNLOCK = 3
PAGE_BACKUP = 4
PAGE_ROOT = 5
PAGE_MODULES = 6
PAGE_RETURN_STOCK = 7
PAGE_FLASH_ROM = 8
PAGE_DIAGNOSTICS = 9
PAGE_MTK_UNISOC = 10
PAGE_DOWNLOADS = 11
PAGE_UNBRICK = 12
PAGE_INTEGRITY = 13
PAGE_LOGS_HELP = 14
PAGE_SIDELOAD = 15


class MainWindow(QMainWindow):
    """Top-level application window."""

    device_changed = Signal(object)
    network_changed = Signal(bool)

    def __init__(
        self,
        config: Config,
        network: NetworkMonitor,
        device_mgr: DeviceManager,
        adb: ADB,
        fastboot: Fastboot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._network = network
        self._device_mgr = device_mgr
        self._adb = adb
        self._fastboot = fastboot
        self._scrcpy_mgr = ScrcpyManager(tools_dir=TOOLS_DIR)
        self._diagnostics_engine = DiagnosticsEngine(adb=self._adb, fastboot=self._fastboot)
        self._monitor_worker = DeviceMonitorWorker(adb=self._adb, fastboot=self._fastboot)
        self._flash_worker = FlashEngineWorker(adb=self._adb, fastboot=self._fastboot)
        self._action_buttons: dict[str, LiquidGlassActionRow] = {}
        self._device_state = DeviceStateBroadcaster(self)
        self._hardware_info: DeviceInfo | None = None
        self._displayed_device: tuple[str, str] | None = None
        self._action_descs: dict[str, str] = {}

        self._init_window()
        self._build_menu_bar()
        self._build_central()
        self._connect_signals()
        self._set_theme(self._config.get("theme", "dark"))
        self._apply_write_safety(False)
        self._handle_device_change(self._device_mgr.device)

        # Kick off an initial network check
        self._network.check_now()

        log.info("MainWindow initialised.")

    # ==================================================================
    # Window setup
    # ==================================================================

    def _init_window(self) -> None:
        self.setWindowTitle(f"{__app_name__} -- Android Service Toolbox")
        w = self._config.get("window_width", 1260)
        h = self._config.get("window_height", 780)
        self.resize(w, h)

        # Restore position if saved
        x = self._config.get("window_x")
        y = self._config.get("window_y")
        if x is not None and y is not None:
            self.move(x, y)

        self.setMinimumSize(900, 600)

        self.setWindowIcon(get_icon("app_logo", 64, color="#FFFFFF"))

    # ==================================================================
    # Menu bar
    # ==================================================================

    def _build_menu_bar(self) -> None:
        menu = self.menuBar()
        menu.setVisible(False)

        # ---- File ----
        file_menu = menu.addMenu("&File")
        file_menu.addAction(self._action("E&xit", self.close, "Ctrl+Q"))

        # ---- Mode ----
        mode_menu = menu.addMenu("&Mode")
        mode_menu.addAction(
            self._action("&Simple mode", partial(self._set_mode, "simple"))
        )
        mode_menu.addAction(
            self._action("&Advanced mode", partial(self._set_mode, "advanced"))
        )
        mode_menu.addSeparator()
        self._dry_run_action = self._action(
            "&Dry-Run mode", self._toggle_dry_run, checkable=True
        )
        self._dry_run_action.setChecked(self._config.dry_run)
        mode_menu.addAction(self._dry_run_action)

        # ---- Device ----
        dev_menu = menu.addMenu("&Device")
        dev_menu.addAction(self._action("&Refresh detection", self._refresh_device))
        dev_menu.addAction(self._action("&Check my phone", lambda: self._on_action("check_phone")))

        # ---- Network ----
        net_menu = menu.addMenu("&Network")
        self._offline_action = self._action(
            "Force &Offline", self._toggle_offline, checkable=True
        )
        self._offline_action.setChecked(self._config.offline_forced)
        net_menu.addAction(self._offline_action)
        net_menu.addAction(self._action("&Check now", self._check_network_now))

        # ---- View (Theme) ----
        view_menu = menu.addMenu("&View")
        theme_menu = view_menu.addMenu("&Theme")
        theme_menu.addAction(self._action("&Dark Theme", partial(self._set_theme, "dark")))
        theme_menu.addAction(self._action("&Light Theme", partial(self._set_theme, "light")))

        # ---- Tools ----
        tools_menu = menu.addMenu("&Tools")
        tools_menu.addAction(self._action("&Preferences & Settings", lambda: self._on_action("settings"), "Ctrl+,"))
        tools_menu.addAction(self._action("&Multi-Mode Power & Reboot Switchboard", self._open_reboot_switchboard))
        tools_menu.addAction(self._action("&Partition Image & Header Inspector", self._open_header_inspector))
        tools_menu.addSeparator()
        tools_menu.addAction(self._action("&Laptop & Workstation Setup Wizard", self._show_setup_wizard))
        tools_menu.addAction(self._action("&Phone Hardware Keys Guide", self._show_key_guide))
        tools_menu.addAction(self._action("&System Health & Self-Test", self._show_selftest))

        # ---- Help ----
        help_menu = menu.addMenu("&Help")
        help_menu.addAction(self._action("&Workflow & Function Guide", self._show_guide))
        help_menu.addAction(self._action("&Laptop Setup Wizard", self._show_setup_wizard))
        help_menu.addAction(self._action("&Phone Hardware Keys Guide", self._show_key_guide))
        help_menu.addAction(self._action("&Preferences & Settings Center", lambda: self._on_action("settings")))
        help_menu.addAction(self._action("&About FlashDock", self._show_about))

    def _action(
        self, text: str, slot=None, shortcut: str = "", checkable: bool = False
    ) -> QAction:
        act = QAction(text, self)
        if slot:
            act.triggered.connect(slot)
        if shortcut:
            act.setShortcut(shortcut)
        act.setCheckable(checkable)
        return act

    # ==================================================================
    # Central widget
    # ==================================================================

    def _build_central(self) -> None:
        central = LiquidGlassCanvas()
        central.setObjectName("centralWorkspace")
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._island = ObsidianDynamicIslandBar(self)
        self._island.lens_control.segment_selected.connect(self._on_category_clicked)
        self._island.write_switch.toggled.connect(self._apply_write_safety)
        self._island.island_pill.clicked.connect(partial(self._on_action, "check_phone"))
        root_layout.addWidget(self._island)

        # ---- Top area: sidebar + content ----
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Phone Control Panel (left sidebar)
        self._phone_panel = PhoneControlPanel()
        self._phone_panel.setObjectName('iosSidebar')
        body.addWidget(self._phone_panel)

        # Center workspace container
        self._center_container = QWidget(self)
        center_lay = QVBoxLayout(self._center_container)
        center_lay.setContentsMargins(0, 0, 0, 0)
        center_lay.setSpacing(0)

        # 1. Live Device State Visualizer & Diagnostics HUD (Section 1)
        self._live_hud = LiveDeviceHud(self)

        # 2. Resizable Horizontal Splitter (Phase 24: 5px grip line, hover styling, non-collapsible)
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._main_splitter.setHandleWidth(5)
        self._main_splitter.setChildrenCollapsible(False)
        # Stacked widget: page 0 = home, page 1 = device card, page 2 = checklist
        self._stack = QStackedWidget(self)
        self._build_home_page()       # PAGE_HOME = 0
        self._build_device_page()     # PAGE_DEVICE_CARD = 1
        self._build_checklist_page()  # PAGE_CHECKLIST = 2
        self._build_unlock_page()     # PAGE_UNLOCK = 3
        self._build_backup_page()     # PAGE_BACKUP = 4
        self._build_root_page()       # PAGE_ROOT = 5
        self._build_modules_page()    # PAGE_MODULES = 6
        self._build_return_stock_page()  # PAGE_RETURN_STOCK = 7
        self._build_flash_rom_page()     # PAGE_FLASH_ROM = 8
        self._build_diagnostics_page()   # PAGE_DIAGNOSTICS = 9
        self._build_mtk_unisoc_page()    # PAGE_MTK_UNISOC = 10
        self._build_downloads_page()     # PAGE_DOWNLOADS = 11
        self._build_unbrick_page()       # PAGE_UNBRICK = 12
        self._build_integrity_page()     # PAGE_INTEGRITY = 13
        self._build_logs_help_page()     # PAGE_LOGS_HELP = 14
        self._build_sideload_page()      # PAGE_SIDELOAD = 15
        self._main_splitter.addWidget(self._stack)

        # Persistent Side Activity Terminal (Phase 24: resizable min 240px, max 600px)
        self._side_terminal = SideTerminalWidget(self)
        self._side_terminal.setMinimumWidth(240)
        self._side_terminal.setMaximumWidth(600)
        self._side_terminal.hide()
        self._side_terminal.collapse_requested.connect(self._toggle_terminal_visibility)
        self._main_splitter.addWidget(self._side_terminal)

        # Explicit default sizing: workspace expands, telemetry default at 320px
        self._main_splitter.setSizes([850, 320])
        self._main_splitter.setStretchFactor(0, 1)
        self._main_splitter.setStretchFactor(1, 0)

        center_lay.addWidget(self._main_splitter, 1)
        body.addWidget(self._center_container, 1)

        root_layout.addLayout(body, 1)

        # ---- Unified bottom footer bar (Device Selector + Status Bar in single row) ----
        self._device_selector = DeviceSelector(self)

        # Action widgets on the device bar
        self._btn_driver_fix = QPushButton("Fix OEM Driver / COM Port")
        self._btn_driver_fix.setIcon(get_icon("tools", 12))
        self._btn_driver_fix.setToolTip("Install missing OEM USB drivers, fix MTK VCOM code 10, or fix Qualcomm 9008 COM port errors")
        self._btn_driver_fix.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_driver_fix.setFixedHeight(28)
        self._btn_driver_fix.clicked.connect(lambda: self._on_action("downloads"))

        # Terminal Toggle Button
        self._btn_terminal_toggle = QPushButton("Hide Terminal")
        self._btn_terminal_toggle.setIcon(get_icon("chevron_right", 12))
        self._btn_terminal_toggle.setToolTip("Hide Live Telemetry Terminal to maximize workspace canvas")
        self._btn_terminal_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_terminal_toggle.setFixedHeight(28)
        self._btn_terminal_toggle.clicked.connect(self._toggle_terminal_visibility)
        self._device_selector.add_action_widget(self._btn_terminal_toggle)

        # Unified single bottom bar hosting telemetry and device controls
        self._status_bar = StatusBarWidget(self, device_selector=self._device_selector)
        self._status_bar._connection_badge.hide()
        self._safety_hint = QLabel("Write controls are locked. Select Write: Safe in the top bar to arm them.")
        self._safety_hint.setWordWrap(True)
        center_lay.insertWidget(0, self._safety_hint)
        self._stack.currentChanged.connect(self._update_safety_hint)
        root_layout.addWidget(self._status_bar)
        self._update_terminal_toggle_ui(False)

    def _build_home_page(self) -> None:
        page = QWidget()
        page.setObjectName("glassHome")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(12)

        header = QHBoxLayout()
        heading = QLabel("Workstation")
        heading.setObjectName("glassHeading")
        header.addWidget(heading, 1)
        self._theme_btn = QPushButton()
        self._theme_btn.clicked.connect(self._toggle_theme)
        header.addWidget(self._theme_btn)
        layout.addLayout(header)

        controls = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search tools and workflows")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._filter_tools)
        self._search_input.returnPressed.connect(self._on_search_return_pressed)
        controls.addWidget(self._search_input, 1)
        search_shortcut = QShortcut(QKeySequence("Ctrl+F"), page)
        search_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        search_shortcut.activated.connect(self._search_input.setFocus)
        self._sort_combo = QComboBox()
        self._sort_combo.addItem("Recommended", "recommended")
        self._sort_combo.addItem("Name A–Z", "az")
        self._sort_combo.addItem("Name Z–A", "za")
        self._sort_combo.currentIndexChanged.connect(self._filter_tools)
        controls.addWidget(self._sort_combo)
        layout.addLayout(controls)
        self._tools_count_badge = QLabel()
        layout.addWidget(self._tools_count_badge)
        self._active_category = "All"
        self._workflow_sheets = {}
        sheets = QHBoxLayout()
        sheets.setSpacing(10)
        actions = {item[0]: item for item in MAIN_ACTIONS}
        glass_icons = {
            "check_phone": "check-phone", "checklist": "safety-checklist",
            "backup": "backup-restore", "diagnostics": "diagnostics-tweaks",
            "sideload": "sideload-apps", "scrcpy": "screen-mirror",
            "root": "root-phone", "modules": "manage-modules",
            "integrity": "fix-play-integrity", "unlock_bl": "unlock-bootloader",
            "flash_rom": "flash-rom", "unbrick": "fix-bricked",
            "mtk_unisoc": "mtk-unisoc", "return_stock": "return-stock",
        }
        for key, title, action_ids in WORKFLOWS:
            sheet = LiquidGlassSheet()
            sheet_layout = QVBoxLayout(sheet)
            sheet_layout.setContentsMargins(6, 10, 6, 6)
            sheet_layout.setSpacing(2)
            label = QLabel(title)
            label.setProperty("glassSectionTitle", True)
            label.setWordWrap(True)
            sheet_layout.addWidget(label)
            self._workflow_sheets[key] = sheet
            for action_id in action_ids:
                _, icon, name, desc, category, _ = actions[action_id]
                row = LiquidGlassActionRow(
                    action_id, glass_icons.get(action_id, icon), name, desc, category, parent=sheet
                )
                row.clicked.connect(partial(self._on_action, action_id))
                sheet.track_row(row)
                self._action_buttons[action_id] = row
                self._action_descs[action_id] = desc
                sheet_layout.addWidget(row)
            sheets.addWidget(sheet, 1, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(sheets)
        self._empty_state_widget = LiquidGlassSheet()
        empty_layout = QHBoxLayout(self._empty_state_widget)
        self._empty_state_msg = QLabel("No tools match your search.")
        empty_layout.addWidget(self._empty_state_msg, 1)
        clear_btn = QPushButton("Reset filters")
        clear_btn.clicked.connect(self._reset_filters)
        empty_layout.addWidget(clear_btn)
        layout.addWidget(self._empty_state_widget)
        layout.addStretch(1)
        missing = [name for name, tool in (("ADB", self._adb), ("Fastboot", self._fastboot))
                   if not tool.available]
        if missing:
            label = QLabel(f"{' and '.join(missing)} unavailable. Install platform-tools in Downloads & Tools.")
            label.setWordWrap(True)
            layout.addWidget(label)
        self._stack.addWidget(page)
        self._filter_tools()

    def _make_back_button(self) -> QPushButton:
        """Create a standard navigation back button adhering to the active theme."""
        btn = QPushButton("← Back to Home")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedWidth(140)
        btn.clicked.connect(lambda: self._on_action("home"))
        return btn

    def _build_device_page(self) -> None:
        """Build the device details page (shown by 'Check my phone')."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 16, 24, 12)
        page_layout.setSpacing(10)

        # Back button
        page_layout.addWidget(self._make_back_button())

        # Title
        title_box = QHBoxLayout()
        title_box.setSpacing(8)
        phone_icon = create_icon_label("phone", size=20)
        title_box.addWidget(phone_icon)
        title = QLabel("Device Details")
        title.setProperty("cssClass", "heading")
        title_box.addWidget(title)
        title_box.addStretch()
        page_layout.addLayout(title_box)

        page_layout.addWidget(self._live_hud)

        # Device card
        self._device_card = DeviceCard()
        page_layout.addWidget(self._device_card, 1)

        self._stack.addWidget(page)

    def _build_checklist_page(self) -> None:
        """Build the checklist page (shown by 'Checklist')."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 16, 24, 12)
        page_layout.setSpacing(10)

        page_layout.addWidget(self._make_back_button())

        # Checklist screen
        self._checklist_screen = ChecklistScreen(adb=self._adb)
        page_layout.addWidget(self._checklist_screen, 1)

        self._stack.addWidget(page)

    def _build_unlock_page(self) -> None:
        """Build the bootloader unlock wizard page."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 16, 24, 12)
        page_layout.setSpacing(10)

        page_layout.addWidget(self._make_back_button())

        # Unlock screen
        self._unlock_screen = UnlockScreen(
            device_mgr=self._device_mgr,
            adb=self._adb,
            fastboot=self._fastboot,
        )
        page_layout.addWidget(self._unlock_screen, 1)

        self._stack.addWidget(page)

    def _build_backup_page(self) -> None:
        """Build the backup and restore manager page."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 16, 24, 12)
        page_layout.setSpacing(10)

        page_layout.addWidget(self._make_back_button())

        # Backup screen
        self._backup_screen = BackupScreen(
            device_mgr=self._device_mgr,
            adb=self._adb,
            fastboot=self._fastboot,
        )
        page_layout.addWidget(self._backup_screen, 1)

        self._stack.addWidget(page)

    def _build_root_page(self) -> None:
        """Build the rooting wizard page."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 16, 24, 12)
        page_layout.setSpacing(10)

        page_layout.addWidget(self._make_back_button())

        # Root screen
        self._root_screen = RootScreen(
            device_mgr=self._device_mgr,
            adb=self._adb,
            fastboot=self._fastboot,
        )
        page_layout.addWidget(self._root_screen, 1)

        self._stack.addWidget(page)

    def _build_modules_page(self) -> None:
        """Build the root modules management page."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 16, 24, 12)
        page_layout.setSpacing(10)

        page_layout.addWidget(self._make_back_button())

        # Modules screen
        self._modules_screen = ModulesScreen(
            device_mgr=self._device_mgr,
            adb=self._adb,
        )
        page_layout.addWidget(self._modules_screen, 1)

        self._stack.addWidget(page)

    def _build_return_stock_page(self) -> None:
        """Build the Return to Stock & Bootloader Relock page."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 16, 24, 12)
        page_layout.setSpacing(10)

        page_layout.addWidget(self._make_back_button())

        # Return to stock screen
        self._return_stock_screen = ReturnStockScreen(
            device_mgr=self._device_mgr,
            adb=self._adb,
            fastboot=self._fastboot,
        )
        page_layout.addWidget(self._return_stock_screen, 1)

        self._stack.addWidget(page)

    def _build_flash_rom_page(self) -> None:
        """Build the Custom ROM, GSI, and Recovery Flashing page."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 16, 24, 12)
        page_layout.setSpacing(10)

        page_layout.addWidget(self._make_back_button())

        # Flash ROM screen
        self._flash_rom_screen = FlashRomScreen(
            device_mgr=self._device_mgr,
            fastboot=self._fastboot,
        )
        page_layout.addWidget(self._flash_rom_screen, 1)

        self._stack.addWidget(page)

    def _build_diagnostics_page(self) -> None:
        """Build the Phase 10 Diagnostics, Debloater & System Tweaks page."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 16, 24, 12)
        page_layout.setSpacing(10)

        page_layout.addWidget(self._make_back_button())

        # Diagnostics screen
        self._diagnostics_screen = DiagnosticsScreen(
            device_mgr=self._device_mgr,
            adb=self._adb,
        )
        page_layout.addWidget(self._diagnostics_screen, 1)

        self._stack.addWidget(page)

    def _build_mtk_unisoc_page(self) -> None:
        """Build the Phase 11 MediaTek BROM & Unisoc PAC Flashing page."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 16, 24, 12)
        page_layout.setSpacing(10)

        page_layout.addWidget(self._make_back_button())

        # MTK & Unisoc screen
        self._mtk_unisoc_screen = MtkUnisocScreen()
        page_layout.addWidget(self._mtk_unisoc_screen, 1)

        self._stack.addWidget(page)

    def _build_downloads_page(self) -> None:
        """Build the Phase 12 Downloads, Drivers & Platform-Tools Manager page."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 16, 24, 12)
        page_layout.setSpacing(10)

        page_layout.addWidget(self._make_back_button())

        # Downloads & Tools screen
        self._downloads_screen = DownloadsScreen(
            device_mgr=self._device_mgr,
            adb=self._adb,
            fastboot=self._fastboot,
        )
        page_layout.addWidget(self._downloads_screen, 1)

        self._stack.addWidget(page)

    def _build_unbrick_page(self) -> None:
        """Build the dedicated Fix Bricked Phone & Bootloop Rescue page."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 16, 24, 12)
        page_layout.setSpacing(10)

        page_layout.addWidget(self._make_back_button())

        # Unbrick & Bootloop screen
        self._unbrick_screen = UnbrickScreen(
            device_mgr=self._device_mgr,
            adb=self._adb,
            fastboot=self._fastboot,
        )
        self._unbrick_screen.navigate_to_page.connect(self._stack.setCurrentIndex)
        page_layout.addWidget(self._unbrick_screen, 1)

        self._stack.addWidget(page)

    def _build_integrity_page(self) -> None:
        """Build the Phase 14 Play Integrity Fixer & Fingerprint Spoofer page."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 16, 24, 12)
        page_layout.setSpacing(10)

        page_layout.addWidget(self._make_back_button())

        # Play Integrity Fixer screen
        self._integrity_screen = IntegrityScreen(
            device_mgr=self._device_mgr,
            adb=self._adb,
        )
        page_layout.addWidget(self._integrity_screen, 1)

        self._stack.addWidget(page)

    def _build_logs_help_page(self) -> None:
        """Build the Phase 15 Logs, Telemetry & Troubleshooting Center page."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 16, 24, 12)
        page_layout.setSpacing(10)

        page_layout.addWidget(self._make_back_button())

        # Logs & Help screen
        self._logs_help_screen = LogsHelpScreen(
            device_mgr=self._device_mgr,
            adb=self._adb,
        )
        self._logs_help_screen.navigate_to_page.connect(self._stack.setCurrentIndex)
        page_layout.addWidget(self._logs_help_screen, 1)

        self._stack.addWidget(page)

    def _build_sideload_page(self) -> None:
        """Build the Phase 23 Universal Sideloading & App Manager page."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 16, 24, 12)
        page_layout.setSpacing(10)

        page_layout.addWidget(self._make_back_button())

        # Sideload & App Manager screen
        self._sideload_screen = SideloadScreen(
            device_mgr=self._device_mgr,
            adb=self._adb,
            parent=page,
        )
        self._sideload_screen.navigate_to_page.connect(self._stack.setCurrentIndex)
        page_layout.addWidget(self._sideload_screen, 1)

        self._stack.addWidget(page)

    def _on_category_clicked(self, key: str) -> None:
        self._active_category = key
        self._island.lens_control.set_active_segment(key)
        self._on_action("home")
        self._filter_tools()

    def _filter_tools(self) -> None:
        query = self._search_input.text().strip().casefold()
        sort = self._sort_combo.currentData()
        actions = {item[0]: item for item in MAIN_ACTIONS}
        count = 0
        for key, _, action_ids in WORKFLOWS:
            sheet = self._workflow_sheets[key]
            sheet_layout = sheet.layout()
            ordered = list(action_ids)
            if sort in ("az", "za"):
                ordered.sort(key=lambda aid: actions[aid][2].casefold(), reverse=sort == "za")
            visible = 0
            for aid in ordered:
                row = self._action_buttons[aid]
                sheet_layout.removeWidget(row)
                sheet_layout.addWidget(row)
                _, _, name, desc, category, tags = actions[aid]
                matches = self._active_category in ("All", key) and any(
                    query in term.casefold() for term in (aid, name, desc, category, *tags)
                )
                row.setVisible(matches)
                visible += matches
            sheet.setVisible(bool(visible))
            count += visible
        self._tools_count_badge.setText(f"{count} of {len(MAIN_ACTIONS)} tools")
        self._empty_state_widget.setVisible(not count)

    def _on_search_return_pressed(self) -> None:
        for row in self._action_buttons.values():
            if row.isVisible() and row.isEnabled():
                row.click()
                break

    def _reset_filters(self) -> None:
        self._active_category = "All"
        self._island.lens_control.set_active_segment("All")
        self._search_input.clear()
        self._sort_combo.setCurrentIndex(0)
        self._filter_tools()

    @Slot(bool)
    def _apply_write_safety(self, armed: bool) -> None:
        # Gate write-capable screens while retaining their existing preflight checks.
        for screen in (
            self._unlock_screen, self._backup_screen, self._root_screen,
            self._modules_screen, self._integrity_screen, self._flash_rom_screen,
            self._return_stock_screen, self._unbrick_screen, self._mtk_unisoc_screen,
            self._sideload_screen,
        ):
            screen.setEnabled(armed)
        self._live_hud.setEnabled(armed)
        self._update_safety_hint(self._stack.currentIndex())

    def _update_safety_hint(self, index: int) -> None:
        write_pages = {
            PAGE_UNLOCK, PAGE_BACKUP, PAGE_ROOT, PAGE_MODULES, PAGE_INTEGRITY,
            PAGE_FLASH_ROM, PAGE_RETURN_STOCK, PAGE_UNBRICK, PAGE_MTK_UNISOC, PAGE_SIDELOAD,
        }
        self._safety_hint.setVisible(index in write_pages and not self._island.write_switch.is_armed)

    # ==================================================================
    # Signal wiring
    # ==================================================================

    def _connect_signals(self) -> None:
        self.network_changed.connect(self._status_bar.update_network, Qt.ConnectionType.QueuedConnection)
        self.network_changed.connect(self._update_network_buttons, Qt.ConnectionType.QueuedConnection)
        self._network.on_change = self.network_changed.emit

        # Wire logger to Side Terminal (User Addition 4)
        terminal_handler = SideTerminalHandler(self._side_terminal.append_line)
        self._side_terminal.set_handler(terminal_handler)
        logging.getLogger("flashdock").addHandler(terminal_handler)

        # DeviceManager polls in a Python thread. Queue UI updates through Qt.
        self.device_changed.connect(self._device_state.publish, Qt.ConnectionType.QueuedConnection)
        self._device_state.state_updated.connect(self._handle_device_change)
        self._device_mgr.on_device_changed = self.device_changed.emit

        # Phone control panel -> device manager & scrcpy & hardware keys
        self._phone_panel.reboot_requested.connect(self._on_reboot_requested)
        self._phone_panel.refresh_requested.connect(self._refresh_device)
        self._phone_panel.switchboard_requested.connect(self._open_reboot_switchboard)
        self._phone_panel.scrcpy_requested.connect(self._launch_scrcpy)
        self._phone_panel.key_event_requested.connect(self._on_key_event_requested)
        self._phone_panel.key_guide_requested.connect(self._show_key_guide)
        self._phone_panel.setup_wizard_requested.connect(self._show_setup_wizard)
        self._phone_panel.restart_adb_requested.connect(self._restart_adb_server)
        self._phone_panel.action_requested.connect(self._on_action)

        # GSM Suite Hardware Monitor Worker
        self._monitor_worker.device_connected.connect(self._on_hardware_device_connected)
        self._monitor_worker.device_disconnected.connect(self._on_hardware_device_disconnected)
        self._monitor_worker.status_message.connect(lambda msg: self._side_terminal.append_colored_stream("INFO", msg))

        # GSM Suite Flash Engine Worker
        self._flash_worker.progress_changed.connect(lambda cur, tot, pct: self._status_bar.set_progress(pct))
        self._flash_worker.status_changed.connect(self._on_flash_status_changed)
        self._flash_worker.log_emitted.connect(lambda lvl, msg: self._side_terminal.append_colored_stream(lvl, msg))
        self._flash_worker.flash_finished.connect(self._on_flash_finished)
        self._flash_worker.started.connect(self._monitor_worker.pause_polling)
        self._flash_worker.started.connect(lambda: self._island.write_switch.setEnabled(False))
        self._flash_worker.finished.connect(lambda: self._island.write_switch.setEnabled(True))
        self._flash_worker.finished.connect(self._monitor_worker.resume_polling)

        # Device selector -> device manager & refresh
        self._device_selector.serial_locked.connect(self._device_mgr.lock_serial)
        self._device_selector.serial_unlocked.connect(self._device_mgr.unlock_serial)
        self._device_selector.refresh_requested.connect(self._refresh_device)

        # Live Device Diagnostics HUD signals
        self._live_hud.restore_preflash_requested.connect(self._on_restore_preflash_requested)

        # Initial status push
        self._status_bar.update_network(self._network.is_online)
        self._status_bar.update_mode(self._mode_display_text())

    # ==================================================================
    # GSM Suite Hardware & Flash Slots
    # ==================================================================

    @Slot(str, str, dict)
    def _on_hardware_device_connected(self, mode: str, ident: str, details: dict) -> None:
        """Handle hardware device connection from background monitor worker."""
        log.info("Hardware monitor detected %s [%s]", mode, ident)
        self._hardware_info = DeviceInfo(
            mode=mode, serial=ident, model=details.get("display_name", "")
        )
        self._update_island(self._device_mgr.device)
        self._phone_panel.set_mode(mode)
        self._side_terminal.append_colored_stream(
            "INFO", f"Device connected: {details.get('display_name', mode)} [{ident}]"
        )

    @Slot()
    def _on_hardware_device_disconnected(self) -> None:
        """Handle hardware disconnection from background monitor worker."""
        if is_flash_locked():
            log.debug("Flash lock active: suppressing hardware disconnection event during active transfer.")
            return
        self._hardware_info = None
        self._side_terminal.append_colored_stream("WARN", "Device disconnected from USB/COM bus.")
        self._handle_device_change(None)

    @Slot(str)
    def _on_flash_status_changed(self, status: str) -> None:
        """Map high-level status messages to stepped pipeline stage HUD tracker."""
        status_l = status.lower()
        if "integrity" in status_l or "checksum" in status_l or "verifying" in status_l:
            self._live_hud.set_stepped_stage(1, status, 25)
        elif "backup" in status_l or "calibration" in status_l or "partition" in status_l:
            self._live_hud.set_stepped_stage(2, status, 50)
        elif "flashing" in status_l or "writing" in status_l or "erase" in status_l:
            self._live_hud.set_stepped_stage(3, status, 75)
        elif "completed" in status_l or "success" in status_l or "verified" in status_l:
            self._live_hud.set_stepped_stage(4, status, 100)
        else:
            self._live_hud.set_stepped_stage(1, status, 10)

    @Slot(bool, str)
    def _on_flash_finished(self, success: bool, message: str) -> None:
        """Handle completion of background flash engine task."""
        self._status_bar.hide_progress()
        if success:
            self._live_hud.reset_pipeline("Operation Complete: Verified")
            self._side_terminal.append_colored_stream("SUCCESS", f"Flashing finished: {message}")
            QMessageBox.information(self, "Flash Complete", f"Operation completed successfully!\n\n{message}")
        else:
            self._live_hud.trigger_failure_alert(message)
            self._side_terminal.append_colored_stream("ERROR", f"Flashing failed: {message}")
            QMessageBox.warning(self, "Flash Failed", f"Operation failed:\n\n{message}")

    @Slot()
    def _open_reboot_switchboard(self) -> None:
        """Open the Universal Multi-Mode Reboot Switchboard modal."""
        dlg = RebootSwitchboardDialog(self._device_mgr.device, self)
        dlg.reboot_mode_selected.connect(self._on_reboot_requested)
        dlg.exec()

    @Slot(str)
    def _on_restore_preflash_requested(self, serial: str) -> None:
        """Execute 1-click Auto-Rescue restoration of pre-flash image dumps."""
        if not self._island.write_switch.is_armed:
            return
        reply = QMessageBox.warning(
            self,
            "Restore Pre-Flash State",
            f"Are you sure you want to restore the pre-flash emergency backup for device [{serial}]?\n\n"
            "This will flash the emergency saved partitions (boot, init_boot, vbmeta, persist, etc.) back to the device.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            ok, msg = self._flash_worker.restore_emergency_preflash(serial)
            if ok:
                QMessageBox.information(self, "Auto-Rescue Success", msg)
            else:
                QMessageBox.critical(self, "Auto-Rescue Failed", msg)

    # ==================================================================
    # Device handling
    # ==================================================================

    def _update_island(self, info: Optional[DeviceInfo]) -> None:
        hardware = self._hardware_info
        if not info or info.mode == "not_connected" or (
            hardware and hardware.mode in {"mtk_brom", "qualcomm_edl", "unisoc_sprd", "mtk_preloader"}
        ):
            info = hardware
        identity = (info.mode, info.serial) if info else None
        if identity != self._displayed_device:
            self._island.write_switch.set_armed(False)
            self._displayed_device = identity
        self._island.island_pill.update_device(info)

    @Slot(object)
    def _handle_device_change(self, info: Optional[DeviceInfo]) -> None:
        """Called on the main thread when the device state changes."""
        self._update_island(info)
        self._live_hud.update_device(info)
        if info and info.mode != "not_connected":
            # Update status bar
            self._status_bar.update_device(info.mode, info.summary_line)

            # Update phone panel
            self._phone_panel.set_mode(info.mode)
            self._phone_panel.set_summary(info.summary_line)
            self._phone_panel.enable_buttons(self._device_mgr.allowed_reboot_targets)

            # Update device selector
            self._device_selector.update_devices(
                self._device_mgr.all_devices,
                self._device_mgr.locked_serial,
            )

            # If on the device card page, refresh it
            if self._stack.currentIndex() == PAGE_DEVICE_CARD:
                self._device_card.update_device(info)
            elif self._stack.currentIndex() == PAGE_FLASH_ROM:
                self._flash_rom_screen.load_for_device(info)
            elif self._stack.currentIndex() == PAGE_DIAGNOSTICS:
                self._diagnostics_screen.load_for_device(info)
            elif self._stack.currentIndex() == PAGE_DOWNLOADS:
                self._downloads_screen.load_for_device(info)
            elif self._stack.currentIndex() == PAGE_UNBRICK:
                self._unbrick_screen.load_for_device(info)
            elif self._stack.currentIndex() == PAGE_INTEGRITY:
                self._integrity_screen.load_for_device(info)
            elif self._stack.currentIndex() == PAGE_LOGS_HELP:
                self._logs_help_screen.load_for_device(info)
            elif self._stack.currentIndex() == PAGE_SIDELOAD:
                self._sideload_screen.load_for_device(info)
        else:
            self._status_bar.update_device("not_connected", "")
            self._phone_panel.set_mode("not_connected")
            self._phone_panel.set_summary("Connect a phone via USB")
            self._phone_panel.enable_buttons([])
            self._device_selector.update_devices([], None)


    @Slot(str)
    def _on_reboot_requested(self, mode: str) -> None:
        """Handle a reboot button click from the Phone Control Panel."""
        if not self._device_mgr.device:
            QMessageBox.warning(self, "No device", "No device is connected.")
            return

        # Confirm for destructive reboots
        mode_label = mode.replace("_", " ").title()
        reply = QMessageBox.question(
            self,
            f"Reboot to {mode_label}?",
            f"Reboot the device to {mode_label} mode?\n\n"
            "Make sure no flash operation is in progress.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        log.info("User confirmed reboot to %s", mode)
        success = self._device_mgr.reboot(mode)
        if not success:
            QMessageBox.warning(
                self, "Reboot failed",
                f"Could not reboot to {mode_label}.\n"
                "Check the log for details."
            )

    @Slot()
    def _refresh_device(self) -> None:
        """Trigger a manual device re-detection."""
        log.info("Manual device refresh requested.")
        info = self._device_mgr.refresh()
        self._handle_device_change(info)

    # ==================================================================
    # Slots / handlers
    # ==================================================================

    def _on_action(self, action_id: str) -> None:
        """Handle a main-menu or sidebar navigation button click."""
        log.info("Action triggered: %s", action_id)

        # Deselect any sticky action cards when navigating
        for card in self._action_buttons.values():
            card.clearFocus()

        # Sync active state in sidebar navigation pills
        if hasattr(self, "_phone_panel"):
            self._phone_panel.set_active_nav(action_id, self._config.get("theme", "dark"))

        if action_id == "home":
            if hasattr(self, "_phone_panel"):
                self._phone_panel.set_active_nav("home", self._config.get("theme", "dark"))
            self._stack.setCurrentIndex(PAGE_HOME)
            return

        if action_id == "settings":
            dlg = SettingsDialog(self._config, self)
            dlg.theme_changed.connect(self._set_theme)
            dlg.exec()
            return

        if action_id == "about":
            self._show_about()
            return

        if action_id == "check_phone":
            # Switch to the device card page and refresh
            info = self._device_mgr.refresh()
            self._device_card.update_device(info)
            self._stack.setCurrentIndex(PAGE_DEVICE_CARD)
            return

        if action_id == "checklist":
            # Switch to checklist page and run checks
            self._checklist_screen.run_checks(self._device_mgr.device)
            self._stack.setCurrentIndex(PAGE_CHECKLIST)
            return

        if action_id == "unlock_bl":
            # Switch to unlock wizard and load for current device
            self._unlock_screen.load_for_device(self._device_mgr.device)
            self._stack.setCurrentIndex(PAGE_UNLOCK)
            return

        if action_id == "backup":
            # Switch to backup & restore manager
            self._backup_screen.load_for_device(self._device_mgr.device)
            self._stack.setCurrentIndex(PAGE_BACKUP)
            return

        if action_id == "root":
            # Switch to rooting wizard
            self._root_screen.load_for_device(self._device_mgr.device)
            self._stack.setCurrentIndex(PAGE_ROOT)
            return

        if action_id == "modules":
            # Switch to root modules management
            self._modules_screen.load_for_device(self._device_mgr.device)
            self._stack.setCurrentIndex(PAGE_MODULES)
            return

        if action_id == "return_stock":
            # Switch to Return to Stock & Safe Relock
            self._return_stock_screen.load_for_device(self._device_mgr.device)
            self._stack.setCurrentIndex(PAGE_RETURN_STOCK)
            return

        if action_id == "flash_rom":
            # Switch to Custom ROM, GSI & Recovery Flasher
            self._flash_rom_screen.load_for_device(self._device_mgr.device)
            self._stack.setCurrentIndex(PAGE_FLASH_ROM)
            return

        if action_id == "diagnostics":
            # Switch to Diagnostics & Tweaks screen
            self._diagnostics_screen.load_for_device(self._device_mgr.device)
            self._stack.setCurrentIndex(PAGE_DIAGNOSTICS)
            return

        if action_id == "mtk_unisoc":
            # Switch to MTK BROM & Unisoc PAC Flashing screen
            self._mtk_unisoc_screen.load_for_device(self._device_mgr.device)
            self._stack.setCurrentIndex(PAGE_MTK_UNISOC)
            return

        if action_id == "unisoc_unlock":
            # Switch to Unlock wizard and load Unisoc brand guide / unlocker
            self._unlock_screen._load_manual_brand("unisoc")
            self._stack.setCurrentIndex(PAGE_UNLOCK)
            return

        if action_id == "downloads":
            # Switch to Phase 12 Downloads, Drivers & Platform-Tools Manager
            self._downloads_screen.load_for_device(self._device_mgr.device)
            self._stack.setCurrentIndex(PAGE_DOWNLOADS)
            return

        if action_id == "unbrick":
            # Switch to dedicated Fix Bricked Phone & Bootloop Rescue screen
            self._unbrick_screen.load_for_device(self._device_mgr.device)
            self._stack.setCurrentIndex(PAGE_UNBRICK)
            return

        if action_id == "integrity":
            # Switch to Phase 14 Play Integrity Fixer & Fingerprint Spoofer screen
            self._integrity_screen.load_for_device(self._device_mgr.device)
            self._stack.setCurrentIndex(PAGE_INTEGRITY)
            return

        if action_id == "scrcpy":
            # Open scrcpy Screen Mirroring & Control dialog
            self._launch_scrcpy()
            return

        if action_id == "logs_help":
            # Switch to Phase 15 Logs, Telemetry & Troubleshooting Center
            self._logs_help_screen.load_for_device(self._device_mgr.device)
            self._stack.setCurrentIndex(PAGE_LOGS_HELP)
            return

        if action_id == "sideload":
            # Switch to Phase 23 Universal Sideloading & App Manager
            self._sideload_screen.load_for_device(self._device_mgr.device)
            self._stack.setCurrentIndex(PAGE_SIDELOAD)
            return

        # All other screens are placeholders until their phase
        screen_name = action_id.replace("_", " ").title()
        msg = (
            'The "{}" screen will be built in a later phase.\n\n'
            "Core features built so far:\n"
            "  - Device detection and summary card\n"
            "  - Phone Control Panel with reboot buttons\n"
            "  - Pre-flash checklist with auto-checks\n"
            "  - Bootloader unlock wizard (brand-aware)\n"
            "  - Safety Engine and Backup / Restore Manager\n"
            "  - Rooting Wizard (Magisk, KernelSU, APatch)\n"
            "  - Root Modules Flasher & Bootloop Recovery"
        ).format(screen_name)
        QMessageBox.information(self, "Coming soon", msg)

    @Slot()
    def _launch_scrcpy(self) -> None:
        """Open the scrcpy Screen Mirroring and control dialog."""
        adb_p = Path(self._adb.binary_path) if self._adb.binary_path else None
        dlg = ScrcpyDialog(
            manager=self._scrcpy_mgr,
            device=self._device_mgr.device,
            adb_path=adb_p,
            parent=self,
        )
        dlg.exec()

    @Slot()
    def _open_header_inspector(self, file_path: str = "") -> None:
        """Open the Partition Image & Header Inspector modal (Hydra / CM2 style)."""
        dlg = PartitionHeaderInspectorDialog(file_path=file_path, parent=self)
        dlg.exec()

    def _set_mode(self, mode: str) -> None:
        self._config.set("app_mode", mode)
        self._status_bar.update_mode(self._mode_display_text())
        log.info("Mode set to %s", mode)

    def _toggle_dry_run(self, checked: bool) -> None:
        self._config.set("dry_run", checked)
        self._status_bar.update_mode(self._mode_display_text())
        log.info("Dry-run %s", "ON" if checked else "OFF")

    def _toggle_offline(self, checked: bool) -> None:
        self._config.set("offline_mode", checked)
        if checked:
            self._status_bar.update_network(False)
        else:
            self._network.check_now()
        log.info("Forced offline %s", "ON" if checked else "OFF")

    def _check_network_now(self) -> None:
        result = self._network.check_now()
        self._status_bar.update_network(result)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            f"About {__app_name__}",
            f"<h2>{__app_name__} v{__version__}</h2>"
            "<p>Personal, one-click Android service toolbox for Windows.</p>"
            "<p>Handles rooting, bootloader unlocking, ROM flashing, "
            "firmware recovery, backup/restore, and returning to stock.</p>"
            "<hr>"
            "<p style='color:#939393;'>For your own devices only.<br>"
            "Test on a spare phone before using on your main device.</p>",
        )

    @Slot()
    def _show_guide(self) -> None:
        """Open the interactive workflow and function guide (Phase 24: interactive launchable cards)."""
        dlg = WorkflowGuideDialog(self)
        dlg.action_requested.connect(self._on_action)
        dlg.exec()

    @Slot()
    def _show_selftest(self) -> None:
        """Open the system diagnostics and self-test dialog (Phase 16)."""
        dlg = SelfTestDialog(self)
        dlg.exec()

    @Slot()
    def _show_setup_wizard(self) -> None:
        """Open the Laptop & Workstation Setup Wizard."""
        dlg = SetupWizardDialog(adb=self._adb, fastboot=self._fastboot, parent=self)
        dlg.exec()

    @Slot()
    def _show_key_guide(self) -> None:
        """Open the phone hardware button navigation guide modal."""
        dev_serial = self._device_mgr.device.serial if (self._device_mgr.device and self._device_mgr.device.serial) else ""
        dlg = HardwareKeyGuideDialog(adb=self._adb, serial=dev_serial, parent=self)
        dlg.exec()

    @Slot(int)
    def _on_key_event_requested(self, keycode: int) -> None:
        """Send virtual hardware key press to connected device via ADB."""
        if not self._device_mgr.device or self._device_mgr.device.mode != "system":
            QMessageBox.information(
                self,
                "Phone Hardware Keys",
                "Virtual hardware key control requires a phone connected in normal System mode with USB debugging enabled.\n\n"
                "If your phone is currently in Bootloader or Recovery mode, use the physical hardware buttons on the phone (see Key Guide).",
            )
            return
        log.info("Sending hardware keycode %d via ADB", keycode)
        try:
            self._adb.shell(f"input keyevent {keycode}", serial=self._device_mgr.device.serial)
        except Exception as e:
            log.warning("Failed to send keycode %d: %s", keycode, e)

    @Slot()
    def _restart_adb_server(self) -> None:
        """Restart the ADB daemon to force re-detection and re-prompt RSA authorization keys."""
        log.info("Restarting ADB server requested from Phone Panel...")
        self._status_bar.show_temporary_message("Restarting ADB server...", timeout=3000)
        try:
            self._adb.kill_server()
            self._adb.start_server()
        except Exception as e:
            log.warning("ADB server restart encountered error: %s", e)
        info = self._device_mgr.refresh()
        self._handle_device_change(info)

    @Slot()
    def _toggle_theme(self) -> None:
        """Toggle between dark and light theme."""
        cur = self._config.get("theme", "dark").lower()
        new_theme = "light" if cur == "dark" else "dark"
        self._set_theme(new_theme)

    @Slot(str)
    def _set_theme(self, theme_name: str) -> None:
        """Apply theme globally and update persistent configuration."""
        theme_name = theme_name.lower()
        self._config.set("theme", theme_name)
        app = QApplication.instance()
        if app:
            stylesheet = get_stylesheet(theme_name)
            if app.styleSheet() != stylesheet:
                app.setStyleSheet(stylesheet)
        if hasattr(self, "_theme_btn"):
            self._theme_btn.setText(self._theme_btn_text(theme_name))
            self._theme_btn.setIcon(get_icon("moon" if theme_name.lower() == "light" else "sun", 14))

        dark = theme_name == "dark"
        self.centralWidget().set_dark_mode(dark)
        self._island.set_dark_mode(dark)
        for sheet in (*self._workflow_sheets.values(), self._empty_state_widget):
            sheet.set_dark_mode(dark)
        for btn in self._action_buttons.values():
            btn.apply_theme(theme_name)
        if self.isVisible():
            self._apply_native_backdrop()
        if hasattr(self, "_phone_panel"):
            self._phone_panel.apply_theme(theme_name)
        if hasattr(self, "_live_hud"):
            self._live_hud.apply_theme(theme_name)
        if hasattr(self, "_sideload_screen"):
            self._sideload_screen.apply_theme(theme_name)
        if hasattr(self, "_device_selector"):
            self._device_selector.apply_theme(theme_name)
        if hasattr(self, "_status_bar"):
            self._status_bar.apply_theme(theme_name)
        if hasattr(self, "_side_terminal"):
            self._update_terminal_toggle_ui(not self._side_terminal.isHidden())

        self._update_network_buttons(self._network.is_online)
        log.info("Theme switched to: %s", theme_name)

    @Slot()
    def _toggle_terminal_visibility(self) -> None:
        """Smoothly toggle Live Telemetry Terminal visibility without splitter glitches (Fix 18)."""
        is_currently_visible = not self._side_terminal.isHidden()
        new_state = not is_currently_visible
        self._side_terminal.setVisible(new_state)
        if new_state:
            self._side_terminal.setMinimumWidth(240)
            self._side_terminal.setMaximumWidth(600)
            self._main_splitter.setSizes([max(600, self.width() - 320), 320])
        self._update_terminal_toggle_ui(new_state)

    def _update_terminal_toggle_ui(self, is_visible: bool | None = None) -> None:
        if is_visible is None:
            is_visible = not self._side_terminal.isHidden()
        self._btn_terminal_toggle.setText("Hide Terminal" if is_visible else "Show Terminal")
        self._btn_terminal_toggle.setToolTip("Toggle live activity and command logs")

    def _theme_btn_text(self, theme: str) -> str:
        return "Dark Mode" if theme.lower() == "light" else "Light Mode"

    @Slot(bool)
    def _update_network_buttons(self, is_online: bool) -> None:
        """Shade or disable buttons requiring internet connection when offline (User Addition 1)."""
        theme = self._config.get("theme", "dark")
        for action in ("downloads", "integrity"):
            self._action_buttons[action].set_offline_state(not is_online, theme)

    def _mode_display_text(self) -> str:
        mode = self._config.get("app_mode", "simple").capitalize()
        if self._config.dry_run:
            return f"{mode} mode -- DRY RUN"
        return f"{mode} mode"

    # ==================================================================
    # Window lifecycle
    # ==================================================================

    def _apply_native_backdrop(self) -> None:
        enabled = enable_windows_acrylic_blur(
            int(self.winId()), self._config.get("theme", "dark") == "dark"
        )
        self.centralWidget().set_native_backdrop(enabled)

    def showEvent(self, event) -> None:  # noqa: N802
        """Handle window show event: start non-blocking hardware polling."""
        super().showEvent(event)
        self._apply_native_backdrop()
        if hasattr(self, "_monitor_worker") and not self._monitor_worker.isRunning():
            self._monitor_worker.start_polling()

    def closeEvent(self, event) -> None:  # noqa: N802
        """Save window geometry and stop background threads."""
        if is_flash_locked():
            reply = QMessageBox.critical(
                self,
                "Flash Operation in Progress",
                "A flash or backup operation is actively writing to device storage!\n\n"
                "Closing FlashDock now can permanently brick your phone.\n\n"
                "Are you sure you want to force close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

        geo = self.geometry()
        self._config.set("window_width", geo.width(), save=False)
        self._config.set("window_height", geo.height(), save=False)
        self._config.set("window_x", geo.x(), save=False)
        self._config.set("window_y", geo.y())
        if hasattr(self, "_monitor_worker") and self._monitor_worker.isRunning():
            self._monitor_worker.stop_polling()
        if hasattr(self, "_flash_worker") and self._flash_worker.isRunning():
            self._flash_worker.cancel()
        self._device_mgr.on_device_changed = None
        self._network.on_change = None
        handler = self._side_terminal._handler_ref
        if handler:
            logging.getLogger("flashdock").removeHandler(handler)
        self._device_mgr.stop()
        self._network.stop()
        log.info("MainWindow closed -- geometry saved.")
        event.accept()
