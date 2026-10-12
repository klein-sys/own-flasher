"""
FlashDock — Main application window.

Assembles the sidebar (Phone Control Panel), the central action area
with the 13 main buttons, device selector, device card, and the status
bar.  Phase 2 wires up real device detection, reboot buttons, and the
"Check my phone" screen.
"""

from __future__ import annotations

import logging
from functools import partial
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QMetaObject, QTimer, Qt, Q_ARG, Slot
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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
from flashdock.ui.styles import get_stylesheet
from flashdock.ui.widgets.device_card import DeviceCard
from flashdock.ui.widgets.device_hud import LiveDeviceHud
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
from flashdock.workers.device_monitor import (
    DeviceMonitorWorker,
    HardwareMode,
    HARDWARE_VID_PID_MAP,
)
from flashdock.workers.flash_engine import (
    FlashEngineWorker,
    FlashOperationType,
    FlashTask,
)
from flashdock.core.diagnostics_engine import (
    DiagnosticsEngine,
    AdbDiagnosticsResult,
    FastbootDiagnosticsResult,
)
from flashdock.ui.icon_assets import create_icon_label, get_icon, get_icon_pixmap

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Category Design Tokens & Card Styling
# ---------------------------------------------------------------------------
CAT_STYLES = {
    "dark": {
        "Root": ("rgba(191, 90, 242, 0.18)", "#BF5AF2"),
        "Flashing": ("rgba(10, 132, 255, 0.18)", "#0A84FF"),
        "Rescue": ("rgba(255, 69, 58, 0.18)", "#FF453A"),
        "Device": ("rgba(48, 209, 88, 0.18)", "#30D158"),
        "Tools": ("rgba(255, 159, 10, 0.18)", "#FF9F0A"),
    },
    "light": {
        "Root": ("rgba(175, 82, 222, 0.15)", "#8944AB"),
        "Flashing": ("rgba(0, 122, 255, 0.15)", "#0071E3"),
        "Rescue": ("rgba(255, 59, 48, 0.15)", "#D70015"),
        "Device": ("rgba(52, 199, 89, 0.15)", "#248A3D"),
        "Tools": ("rgba(255, 149, 0, 0.15)", "#C96E00"),
    },
}

VIBRANT_BADGE_GRADIENTS = {
    "Flashing": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0A84FF, stop:1 #0056B3)",
    "Root": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #BF5AF2, stop:1 #7B2CBF)",
    "Rescue": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #FF453A, stop:1 #C92A2A)",
    "Device": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #30D158, stop:1 #1E824C)",
    "Tools": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #FF9F0A, stop:1 #D35400)",
}

# Distinct, high-vibrancy gradients for each individual workstation action card
ACTION_BADGE_GRADIENTS = {
    # ADB & Device Inspection
    "check_phone":  "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00E5FF, stop:1 #0097A7)",
    "diagnostics":  "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00B4D8, stop:1 #0077B6)",
    "downloads":    "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #10B981, stop:1 #059669)",
    "scrcpy":       "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6366F1, stop:1 #4338CA)",
    "logs_help":    "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #8B5CF6, stop:1 #6D28D9)",

    # Flashing & Bootloader
    "flash_rom":    "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2563EB, stop:1 #1D4ED8)",
    "unlock_bl":    "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F59E0B, stop:1 #D97706)",
    "return_stock": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0284C7, stop:1 #0369A1)",
    "mtk_unisoc":   "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EA580C, stop:1 #C2410C)",

    # Root, Modules & Integrity
    "root":         "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #A855F7, stop:1 #7E22CE)",
    "modules":      "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EC4899, stop:1 #BE185D)",
    "integrity":    "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3B82F6, stop:1 #1E40AF)",

    # Rescue & Safety Prerequisites
    "checklist":    "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #059669, stop:1 #047857)",
    "backup":       "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F97316, stop:1 #C2410C)",
    "unbrick":      "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EF4444, stop:1 #B91C1C)",
}

ACTION_ICON_MAP = {
    "check_phone": "search",
    "checklist": "checklist",
    "unlock_bl": "unlock",
    "root": "root",
    "flash_rom": "flash",
    "modules": "modules",
    "diagnostics": "diagnostics",
    "integrity": "integrity",
    "backup": "backup",
    "unbrick": "unbrick",
    "return_stock": "return_stock",
    "mtk_unisoc": "mtk_unisoc",
    "scrcpy": "scrcpy",
    "downloads": "downloads",
    "logs_help": "logs_help",
}


class ActionCardButton(QPushButton):
    """Next-Gen HyperOS / iOS 18 Action Card with 30x30px vibrant circular badge, continuous squircle curvature and smooth drop shadow."""

    def __init__(
        self,
        action_id: str,
        icon: str,
        label: str,
        desc: str,
        category: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.action_id = action_id
        self.icon_str = icon
        self.label_str = label
        self.desc_str = desc
        self.category = category
        self.setProperty("cssClass", "action")
        self.setToolTip(desc)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(82)

        # Smooth macOS Sequoia Drop Shadow (offset: 0, 4; blur: 16)
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(16)
        self._shadow.setXOffset(0)
        self._shadow.setYOffset(4)
        self._shadow.setColor(QColor(0, 0, 0, 35))
        self.setGraphicsEffect(self._shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 16, 12)
        layout.setSpacing(12)

        # Left Circular Badge Container (30x30px circular chip, border-radius: 15px)
        self.chip_frame = QFrame()
        self.chip_frame.setFixedSize(30, 30)
        self.chip_frame.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        chip_layout = QHBoxLayout(self.chip_frame)
        chip_layout.setContentsMargins(0, 0, 0, 0)
        chip_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(16, 16)
        self.icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        chip_layout.addWidget(self.icon_lbl)
        layout.addWidget(self.chip_frame, 0, Qt.AlignmentFlag.AlignVCenter)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(3)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        self.title_lbl = QLabel(label)
        self.title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        header_row.addWidget(self.title_lbl, 1)

        self.badge_lbl = QLabel(category.upper())
        self.badge_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        header_row.addWidget(self.badge_lbl)
        content_layout.addLayout(header_row)

        self.desc_lbl = QLabel(desc)
        self.desc_lbl.setWordWrap(True)
        self.desc_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        content_layout.addWidget(self.desc_lbl)
        layout.addLayout(content_layout, 1)

    def apply_theme(self, theme: str) -> None:
        theme = theme.lower()
        cat_info = CAT_STYLES.get(theme, CAT_STYLES["dark"]).get(
            self.category, ("rgba(255, 255, 255, 0.08)", "#8E8E93")
        )
        bg_tint, text_color = cat_info

        # Vibrant unique accent gradient for this specific action card
        grad = ACTION_BADGE_GRADIENTS.get(
            self.action_id,
            VIBRANT_BADGE_GRADIENTS.get(
                self.category,
                "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0A84FF, stop:1 #0056B3)",
            ),
        )
        self.chip_frame.setStyleSheet(
            f"background: {grad}; border-radius: 15px; border: none;"
        )

        # High-res vector SVG icon rendered in crisp white inside the badge
        icon_name = ACTION_ICON_MAP.get(self.action_id, self.icon_str or "flash")
        pix = get_icon_pixmap(icon_name, width=16, height=16, color="#FFFFFF")
        self.icon_lbl.setPixmap(pix)

        if theme == "light":
            self.setStyleSheet(
                "QPushButton { background-color: #ECEFF4; border: 1px solid #CBD1DC; border-radius: 16px; }"
                "QPushButton:hover { background-color: #F4F6F9; border-color: #007AFF; }"
                "QPushButton:pressed { background-color: #D8DCE4; }"
            )
            self._shadow.setColor(QColor(0, 0, 0, 15))
            self.title_lbl.setStyleSheet(
                "font-size: 13px; font-weight: 600; color: #1C2024; background: transparent;"
            )
            self.desc_lbl.setStyleSheet(
                "font-size: 11px; color: #5A6572; background: transparent;"
            )
        else:
            self.setStyleSheet(
                "QPushButton { background-color: #1A212E; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; }"
                "QPushButton:hover { background-color: #222C3D; border-color: #0A84FF; }"
                "QPushButton:pressed { background-color: #161D28; }"
            )
            self._shadow.setColor(QColor(0, 0, 0, 80))
            self.title_lbl.setStyleSheet(
                "font-size: 13px; font-weight: 600; color: #E6EDF3; background: transparent;"
            )
            self.desc_lbl.setStyleSheet(
                "font-size: 11px; color: #8B949E; background: transparent;"
            )

        self.badge_lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 6px; "
            f"background-color: {bg_tint}; color: {text_color};"
        )

    def set_offline_state(self, is_offline: bool, theme: str) -> None:
        if is_offline:
            self.setEnabled(False)
            self.setCursor(Qt.CursorShape.ForbiddenCursor)
            self.setToolTip("[Offline] Internet connection required for this function.")
            if theme.lower() == "light":
                self.setStyleSheet(
                    "QPushButton { background-color: #F4F4F5; border: 1px dashed #D4D4D8; "
                    "border-radius: 10px; color: #A1A1AA; }"
                )
            else:
                self.setStyleSheet(
                    "QPushButton { background-color: #141416; border: 1px dashed #2C2C2E; "
                    "border-radius: 10px; color: #555558; }"
                )
        else:
            self.setEnabled(True)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip(self.desc_str)
            self.setStyleSheet("")
            self.apply_theme(theme)


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
    ("integrity",     "integrity",    "Fix Play Integrity",     "Play Integrity diagnosis & fingerprint fixer", "Root", ["integrity", "play integrity", "safetynet", "cts", "banking", "fingerprint", "fix"]),
    ("backup",        "backup",       "Backup / Restore",       "Partition dumps, ADB backups & restore manager", "Rescue", ["backup", "restore", "dump", "partitions", "adb backup", "twrp", "images", "extract"]),
    ("unbrick",       "unbrick",      "Fix bricked phone",      "Emergency rescue: bootloop killer, slot rollback", "Rescue", ["unbrick", "bootloop", "brick", "rescue", "edl", "fix bootloop", "safe mode", "slot", "vbmeta", "stuck"]),
    ("return_stock",  "return_stock", "Return to Stock",        "Remove root, relock & reflash stock firmware", "Flashing", ["stock", "return", "relock", "unroot", "factory", "oem", "revert", "clean"]),
    ("mtk_unisoc",    "mtk_unisoc",   "MTK / Unisoc mode",     "MediaTek BROM, scatter files & PAC flashing", "Flashing", ["mtk", "mediatek", "unisoc", "brom", "scatter", "pac", "bflash", "preloader"]),
    ("scrcpy",        "scrcpy",       "Screen Mirror (scrcpy)", "Ultra-low latency screen mirror, touch control & audio forwarding", "Device", ["scrcpy", "mirror", "screen", "display", "remote", "touch", "record", "audio"]),
    ("downloads",     "downloads",    "Downloads & Tools",     "Platform-tools, OEM drivers & firmware repos", "Device", ["downloads", "drivers", "platform-tools", "adb", "fastboot", "usb", "firmware", "gsi"]),
    ("logs_help",     "logs_help",    "Logs & Help",            "View telemetry logs, guides & troubleshooting", "Device", ["logs", "help", "guide", "troubleshooting", "terminal", "support", "docs"]),
]

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


class MainWindow(QMainWindow):
    """Top-level application window."""

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
        self._action_buttons: dict[str, QPushButton] = {}
        self._action_descs: dict[str, str] = {}

        self._init_window()
        self._build_menu_bar()
        self._build_central()
        self._connect_signals()

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

        # Set high-resolution squircle window icon
        from pathlib import Path
        from PySide6.QtGui import QIcon
        icon_candidates = [
            Path(__file__).resolve().parent.parent / "resources" / "icon.png",
            Path(__file__).resolve().parent.parent.parent / "resources" / "icon.png",
        ]
        for icp in icon_candidates:
            if icp.is_file():
                self.setWindowIcon(QIcon(str(icp)))
                break

    # ==================================================================
    # Menu bar
    # ==================================================================

    def _build_menu_bar(self) -> None:
        menu = self.menuBar()

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
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ---- Device selector bar ----
        self._device_selector = DeviceSelector()
        root_layout.addWidget(self._device_selector)

        # ---- Top Navigation Bar: GSM Suite Segmented Control ----
        self._top_segmented_bar = self._build_top_segmented_bar()
        root_layout.addWidget(self._top_segmented_bar)

        # ---- Top area: sidebar + content ----
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Phone Control Panel (left sidebar)
        self._phone_panel = PhoneControlPanel()
        body.addWidget(self._phone_panel)

        # Center workspace container
        self._center_container = QWidget(self)
        center_lay = QVBoxLayout(self._center_container)
        center_lay.setContentsMargins(0, 0, 0, 0)
        center_lay.setSpacing(0)

        # 1. Live Device State Visualizer & Diagnostics HUD (Section 1)
        self._live_hud = LiveDeviceHud(self)
        center_lay.addWidget(self._live_hud)

        # 2. Resizable Horizontal Splitter (Section 4.4)
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._main_splitter.setHandleWidth(5)
        self._main_splitter.setStyleSheet("""
            QSplitter::handle {
                background: rgba(142, 142, 147, 0.15);
            }
            QSplitter::handle:hover {
                background: #0A84FF;
            }
        """)

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
        self._main_splitter.addWidget(self._stack)

        # Persistent Side Activity Terminal (User Addition 4)
        self._side_terminal = SideTerminalWidget(self)
        self._main_splitter.addWidget(self._side_terminal)

        # Stretch factor: 70% workspace, 30% side terminal
        self._main_splitter.setStretchFactor(0, 7)
        self._main_splitter.setStretchFactor(1, 3)

        center_lay.addWidget(self._main_splitter, 1)
        body.addWidget(self._center_container, 1)

        root_layout.addLayout(body, 1)

        # ---- Status bar (bottom) ----
        self._status_bar = StatusBarWidget(self)
        root_layout.addWidget(self._status_bar)

    def _build_top_segmented_bar(self) -> QWidget:
        """Build the GSM Suite segmented control bar for high-volume OEMs and Universal Chipsets."""
        self._seg_frame = QFrame()
        self._seg_frame.setFixedHeight(38)
        self._seg_frame.setProperty("cssClass", "segmented_control")
        seg_layout = QHBoxLayout(self._seg_frame)
        seg_layout.setContentsMargins(0, 0, 0, 0)
        seg_layout.setSpacing(6)

        label = QLabel("GSM SUITE:")
        label.setStyleSheet("font-size: 11px; font-weight: 700; color: #8E8E93; letter-spacing: 0.5px;")
        seg_layout.addWidget(label)

        self._gsm_segments = [
            ("Xiaomi", "xiaomi", "Xiaomi / POCO / Redmi (MIUI & HyperOS)"),
            ("Samsung", "samsung", "Samsung Galaxy (One UI, Knox, Odin)"),
            ("Transsion", "transsion", "Tecno (HiOS), Infinix (XOS), itel (itelOS)"),
            ("Universal Android", "universal", "AOSP, Pixel, OnePlus, Motorola, Treble GSIs"),
            ("MediaTek BROM", "mtk_brom", "MTK Helio/Dimensity BootROM & Preloader (BROM/DA)"),
            ("Qualcomm EDL", "qualcomm_edl", "Snapdragon Emergency Download 9008 (EDL/Firehose)"),
            ("Unisoc SPRD", "unisoc_sprd", "Spreadtrum / Unisoc Diag & FDL Download Mode"),
        ]

        self._gsm_btn_group: dict[str, QPushButton] = {}
        for title, key, desc in self._gsm_segments:
            btn = QPushButton(title)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(desc)
            btn.clicked.connect(lambda checked, k=key, t=title: self._on_gsm_segment_selected(k, t))
            seg_layout.addWidget(btn)
            self._gsm_btn_group[key] = btn

        seg_layout.addStretch()

        self._btn_driver_fix = QPushButton("Fix OEM Driver / COM Port")
        self._btn_driver_fix.setIcon(get_icon("tools", 12))
        self._btn_driver_fix.setToolTip("Install missing OEM USB drivers, fix MTK VCOM code 10, or fix Qualcomm 9008 COM port errors")
        self._btn_driver_fix.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_driver_fix.setStyleSheet("""
            QPushButton {
                background: rgba(255, 159, 10, 0.15);
                color: #FF9F0A;
                border: 1px solid rgba(255, 159, 10, 0.4);
                border-radius: 6px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(255, 159, 10, 0.3);
            }
        """)
        self._btn_driver_fix.clicked.connect(lambda: self._on_action("downloads"))
        seg_layout.addWidget(self._btn_driver_fix)

        self._update_gsm_segments_style()
        return self._seg_frame

    def _update_gsm_segments_style(self) -> None:
        """Update top GSM segmented bar colors according to current theme."""
        if not hasattr(self, "_seg_frame") or not hasattr(self, "_gsm_btn_group"):
            return
        theme = self._config.get("theme", "dark").lower()
        if theme == "light":
            self._seg_frame.setStyleSheet(
                "background-color: #EBEBEF; border-bottom: 1px solid #D2D2D7; padding: 2px 14px;"
            )
            btn_style = (
                "QPushButton { background: transparent; border: 1px solid rgba(0, 0, 0, 0.12); "
                "border-radius: 6px; padding: 3px 10px; font-size: 11px; font-weight: 500; color: #1D1D1F; } "
                "QPushButton:checked { background: #007AFF; color: #FFFFFF; font-weight: 600; border-color: #007AFF; } "
                "QPushButton:hover:!checked { background: rgba(0, 122, 255, 0.08); color: #007AFF; }"
            )
        else:
            self._seg_frame.setStyleSheet(
                "background-color: #1E1E20; border-bottom: 1px solid #2C2C2E; padding: 2px 14px;"
            )
            btn_style = (
                "QPushButton { background: transparent; border: 1px solid rgba(255, 255, 255, 0.12); "
                "border-radius: 6px; padding: 3px 10px; font-size: 11px; font-weight: 500; color: #E5E5EA; } "
                "QPushButton:checked { background: #0A84FF; color: #FFFFFF; font-weight: 600; border-color: #0A84FF; } "
                "QPushButton:hover:!checked { background: rgba(10, 132, 255, 0.15); color: #0A84FF; }"
            )
        for btn in self._gsm_btn_group.values():
            btn.setStyleSheet(btn_style)

    @Slot(str, str)
    def _on_gsm_segment_selected(self, key: str, title: str) -> None:
        """Handle switching between GSM Suite chipset and OEM profiles."""
        for k, btn in self._gsm_btn_group.items():
            btn.setChecked(k == key)

        self._side_terminal.append_colored_stream("INFO", f"Active GSM Suite Profile: {title}")

        if key == "xiaomi":
            self._stack.setCurrentIndex(PAGE_UNLOCK)
            self._unlock_screen._load_manual_brand("xiaomi")
        elif key == "samsung":
            self._stack.setCurrentIndex(PAGE_RETURN_STOCK)
        elif key == "transsion":
            self._stack.setCurrentIndex(PAGE_UNLOCK)
            self._unlock_screen._load_manual_brand("tecno")
        elif key == "universal":
            self._stack.setCurrentIndex(PAGE_FLASH_ROM)
        elif key == "mtk_brom":
            self._stack.setCurrentIndex(PAGE_MTK_UNISOC)
        elif key == "qualcomm_edl":
            self._stack.setCurrentIndex(PAGE_UNBRICK)
        elif key == "unisoc_sprd":
            self._stack.setCurrentIndex(PAGE_MTK_UNISOC)

    def _build_home_page(self) -> None:
        """Build the home screen with search, category filtering, quick access presets and 14 action cards."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(28, 20, 28, 16)
        page_layout.setSpacing(12)

        # ---- Title Header Row with Guide Button ----
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        title_box = QHBoxLayout()
        title_box.setSpacing(8)
        app_logo_lbl = create_icon_label("app_logo", size=24)
        title_box.addWidget(app_logo_lbl)
        title = QLabel(__app_name__)
        title.setProperty("cssClass", "heading")
        title_box.addWidget(title)
        title_box.addStretch()
        title_col.addLayout(title_box)

        subtitle = QLabel("Unified personal workstation for rooting, flashing, and diagnostics.")
        subtitle.setProperty("cssClass", "muted")
        title_col.addWidget(subtitle)
        top_bar.addLayout(title_col, 1)

        # Setup Laptop button (User Request)
        setup_btn = QPushButton("Setup Laptop")
        setup_btn.setIcon(get_icon("tools", 14))
        setup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        setup_btn.setToolTip("Configure laptop prerequisites, install ADB, Fastboot & OEM USB drivers")
        setup_btn.clicked.connect(self._show_setup_wizard)
        top_bar.addWidget(setup_btn)

        # Phone Key Guide button (User Request)
        key_guide_btn = QPushButton("Key Guide")
        key_guide_btn.setIcon(get_icon("phone", 14))
        key_guide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        key_guide_btn.setToolTip("Hardware button combinations (Vol+, Vol-, Power) for boot menus")
        key_guide_btn.clicked.connect(self._show_key_guide)
        top_bar.addWidget(key_guide_btn)

        # Guide button (User Addition 7)
        guide_btn = QPushButton("Workflow Guide")
        guide_btn.setIcon(get_icon("book", 14))
        guide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        guide_btn.setToolTip("View recommended safe workflows and function explanations")
        guide_btn.clicked.connect(self._show_guide)
        top_bar.addWidget(guide_btn)

        # Self-Test button (Phase 16)
        selftest_btn = QPushButton("Self-Test")
        selftest_btn.setIcon(get_icon("flash", 14))
        selftest_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        selftest_btn.setToolTip("Run automated system diagnostics & toolchain integrity checks")
        selftest_btn.clicked.connect(self._show_selftest)
        top_bar.addWidget(selftest_btn)

        # Dark/Light Theme toggle button
        current_theme = self._config.get("theme", "dark")
        self._theme_btn = QPushButton(self._theme_btn_text(current_theme))
        self._theme_btn.setIcon(get_icon("moon" if current_theme.lower() == "light" else "sun", 14))
        self._theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme_btn.setToolTip("Toggle between Dark and Light mode")
        self._theme_btn.clicked.connect(self._toggle_theme)
        top_bar.addWidget(self._theme_btn)

        page_layout.addLayout(top_bar)

        # ---- Tool availability notice ----
        tool_parts = []
        if not self._adb.available:
            tool_parts.append("ADB not found")
        if not self._fastboot.available:
            tool_parts.append("Fastboot not found")
        if tool_parts:
            tool_warn_frame = QFrame()
            tool_warn_frame.setStyleSheet(
                "background-color: rgba(255, 149, 0, 0.08); border: 1px solid rgba(255, 149, 0, 0.25); "
                "border-radius: 8px; padding: 10px 14px;"
            )
            warn_lay = QHBoxLayout(tool_warn_frame)
            warn_lay.setContentsMargins(4, 4, 4, 4)
            warn_lay.setSpacing(8)
            warn_icon = create_icon_label("warning", 16, color="#C96E00")
            warn_lay.addWidget(warn_icon)
            tool_warn = QLabel(
                ", ".join(tool_parts) + ". "
                "Install Android platform-tools or use Downloads & Updates > Tools Manager."
            )
            tool_warn.setWordWrap(True)
            tool_warn.setStyleSheet("color: #C96E00; font-size: 12px; border: none; background: transparent;")
            warn_lay.addWidget(tool_warn, 1)
            page_layout.addWidget(tool_warn_frame)

        # ---- Search Bar & Filter Navigation Hub ----
        nav_hub = QFrame()
        nav_hub.setStyleSheet("background: transparent;")
        nav_hub_layout = QVBoxLayout(nav_hub)
        nav_hub_layout.setContentsMargins(0, 0, 0, 0)
        nav_hub_layout.setSpacing(10)

        # 1. Search Bar with Clear Button & Keyboard Shortcut
        search_row = QHBoxLayout()
        search_row.setSpacing(10)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(
            "Search tools, actions or keywords (e.g. bootloop, root, flash, debloat, drivers, unbrick)..."
        )
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setMinimumHeight(38)
        self._search_input.textChanged.connect(self._filter_tools)
        self._search_input.returnPressed.connect(self._on_search_return_pressed)
        search_row.addWidget(self._search_input, 1)

        # Quick shortcut Ctrl+F to focus search
        search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        search_shortcut.activated.connect(self._search_input.setFocus)

        nav_hub_layout.addLayout(search_row)
        self._quick_buttons = []

        # 3. Category Filter Pills, Sort Dropdown & Count Badge
        filter_row = QHBoxLayout()
        filter_row.setSpacing(4)

        self._active_category = "All"
        self._cat_buttons = {}
        all_count = len(MAIN_ACTIONS)
        root_count = len([a for a in MAIN_ACTIONS if len(a) > 4 and a[4] == "Root"])
        flash_count = len([a for a in MAIN_ACTIONS if len(a) > 4 and a[4] == "Flashing"])
        rescue_count = len([a for a in MAIN_ACTIONS if len(a) > 4 and a[4] == "Rescue"])
        dev_count = len([a for a in MAIN_ACTIONS if len(a) > 4 and a[4] == "Device"])

        categories = [
            ("All", "globe", f"All ({all_count})"),
            ("Root", "root", f"Root ({root_count})"),
            ("Flashing", "flash", f"Flashing ({flash_count})"),
            ("Rescue", "unbrick", f"Rescue ({rescue_count})"),
            ("Device", "diagnostics", f"Device ({dev_count})"),
        ]

        for cat_key, cat_icon, cat_label in categories:
            c_btn = QPushButton(cat_label)
            c_btn.setIcon(get_icon(cat_icon, 13))
            c_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            c_btn.setStyleSheet("padding: 5px 10px; font-size: 11px;")
            c_btn.clicked.connect(partial(self._on_category_clicked, cat_key))
            filter_row.addWidget(c_btn)
            self._cat_buttons[cat_key] = c_btn

        filter_row.addSpacing(6)

        # Sort selector (User Request: "in all tools sort them also")
        sort_lbl = QLabel("Sort:")
        sort_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #8E8E93;")
        filter_row.addWidget(sort_lbl)

        self._sort_combo = QComboBox()
        self._sort_combo.setMinimumWidth(125)
        self._sort_combo.addItem("Recommended", "recommended")
        self._sort_combo.addItem("Alphabetical (A → Z)", "az")
        self._sort_combo.addItem("Alphabetical (Z → A)", "za")
        self._sort_combo.addItem("Group by Category", "category")
        self._sort_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sort_combo.setToolTip("Sort all tools alphabetically, by category, or recommended order")
        self._sort_combo.currentIndexChanged.connect(self._filter_tools)
        filter_row.addWidget(self._sort_combo)

        filter_row.addStretch(1)

        self._tools_count_badge = QLabel(f"{all_count} tools available")
        self._tools_count_badge.setStyleSheet("font-size: 12px; color: #8E8E93; font-weight: 500;")
        filter_row.addWidget(self._tools_count_badge)

        nav_hub_layout.addLayout(filter_row)
        page_layout.addWidget(nav_hub)

        # ---- Scrollable dynamic grid of action cards ----
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        grid_container = QWidget()
        grid_container.setStyleSheet("background: transparent;")
        grid_layout = QVBoxLayout(grid_container)
        grid_layout.setContentsMargins(0, 4, 0, 0)
        grid_layout.setSpacing(12)

        self._tools_grid = QGridLayout()
        self._tools_grid.setSpacing(14)
        self._tools_grid.setContentsMargins(0, 0, 0, 0)
        grid_layout.addLayout(self._tools_grid)

        # Build each card
        for item in MAIN_ACTIONS:
            action_id = item[0]
            icon = item[1]
            label = item[2]
            desc = item[3]
            category = item[4] if len(item) > 4 else "Device"
            self._make_action_button(action_id, icon, label, desc, category)

        # Empty state display if search has 0 results
        self._empty_state_widget = QFrame()
        self._empty_state_widget.setStyleSheet(
            "background-color: rgba(255, 255, 255, 0.03); border: 1px dashed rgba(255, 255, 255, 0.15); "
            "border-radius: 12px; padding: 28px;"
        )
        empty_box = QVBoxLayout(self._empty_state_widget)
        empty_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_box.setSpacing(8)

        empty_icon = create_icon_label("search", size=32, color="#8E8E93")
        empty_box.addWidget(empty_icon, 0, Qt.AlignmentFlag.AlignCenter)

        self._empty_state_msg = QLabel("No tools match your search or filter.")
        self._empty_state_msg.setStyleSheet("font-size: 13px; color: #8E8E93; font-weight: 500;")
        self._empty_state_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_box.addWidget(self._empty_state_msg)

        clear_btn = QPushButton("Clear Search & Reset Filters")
        clear_btn.setIcon(get_icon("refresh", 14, color="#FFFFFF"))
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet(
            "background-color: #0A84FF; color: #FFFFFF; font-weight: 600; "
            "padding: 6px 16px; border-radius: 8px;"
        )
        clear_btn.clicked.connect(self._reset_filters)
        empty_box.addWidget(clear_btn, 0, Qt.AlignmentFlag.AlignCenter)

        self._empty_state_widget.setVisible(False)
        grid_layout.addWidget(self._empty_state_widget)

        scroll.setWidget(grid_container)
        page_layout.addWidget(scroll, 1)

        # Initial layout & style application
        self._update_category_buttons_style()
        self._update_quick_buttons_style()
        self._update_search_style()
        self._filter_tools()

        # ---- First-run warning ----
        if self._config.first_run:
            warn_card = QFrame()
            warn_card.setStyleSheet(
                "background-color: #121008; border: 1px solid #332508; "
                "border-radius: 8px; padding: 10px 14px;"
            )
            warn_card_lay = QHBoxLayout(warn_card)
            warn_card_lay.setContentsMargins(4, 4, 4, 4)
            warn_card_lay.setSpacing(8)
            warn_icon_lbl = create_icon_label("warning", 16, color="#eab308")
            warn_card_lay.addWidget(warn_icon_lbl)
            warn = QLabel(
                "This tool can modify your phone's firmware. "
                "Always test on a spare phone first. "
                "See Logs & Help for the full disclaimer."
            )
            warn.setWordWrap(True)
            warn.setStyleSheet("color: #eab308; font-size: 12px; border: none; background: transparent;")
            warn_card_lay.addWidget(warn, 1)
            page_layout.addWidget(warn_card)

        self._stack.addWidget(page)

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

    def _make_action_button(
        self, action_id: str, icon: str, label: str, desc: str, category: str = "Device"
    ) -> ActionCardButton:
        """Create one of the main action card buttons."""
        card = ActionCardButton(action_id, icon, label, desc, category)
        card.clicked.connect(partial(self._on_action, action_id))
        cur_theme = self._config.get("theme", "dark")
        card.apply_theme(cur_theme)

        self._action_buttons[action_id] = card
        self._action_descs[action_id] = desc
        return card

    # ------------------------------------------------------------------
    # Home Filter & Search Handlers
    # ------------------------------------------------------------------

    def _on_category_clicked(self, cat_key: str) -> None:
        """Handle category filter pill click."""
        self._active_category = cat_key
        self._update_category_buttons_style()
        self._filter_tools()

    def _update_category_buttons_style(self) -> None:
        """Apply HyperOS 2.0 / iOS 18 pill navigation styling to category buttons."""
        cur_theme = self._config.get("theme", "dark").lower()
        for key, btn in getattr(self, "_cat_buttons", {}).items():
            is_active = (key == getattr(self, "_active_category", "All"))
            if is_active:
                if cur_theme == "light":
                    btn.setStyleSheet(
                        "QPushButton { background: #007AFF; color: #FFFFFF; border: 1px solid #007AFF; "
                        "border-radius: 14px; padding: 6px 14px; font-size: 12px; font-weight: 600; min-height: 24px; }"
                    )
                else:
                    btn.setStyleSheet(
                        "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0A84FF, stop:1 #0056B3); "
                        "color: #FFFFFF; border: 1px solid #3399FF; border-radius: 14px; padding: 6px 14px; font-size: 12px; "
                        "font-weight: 600; min-height: 24px; }"
                    )
            else:
                if cur_theme == "light":
                    btn.setStyleSheet(
                        "QPushButton { background-color: #E2E6EC; color: #1C2024; border: 1px solid #CBD1DC; "
                        "border-radius: 14px; padding: 6px 14px; font-size: 12px; font-weight: 500; min-height: 24px; } "
                        "QPushButton:hover { background-color: #ECEFF4; border-color: #9AA4B2; color: #1C2024; }"
                    )
                else:
                    btn.setStyleSheet(
                        "QPushButton { background-color: #181E26; color: #8B949E; border: 1px solid #2C3644; "
                        "border-radius: 14px; padding: 6px 14px; font-size: 12px; font-weight: 500; min-height: 24px; } "
                        "QPushButton:hover { background-color: #222A36; color: #FFFFFF; border-color: #3D4B5C; }"
                    )

    def _update_quick_buttons_style(self) -> None:
        """Apply theme styling to quick access preset chips."""
        cur_theme = self._config.get("theme", "dark").lower()
        for btn in getattr(self, "_quick_buttons", []):
            if cur_theme == "light":
                btn.setStyleSheet(
                    "QPushButton { background: rgba(0, 0, 0, 0.04); border: 1px solid rgba(0, 0, 0, 0.08); "
                    "border-radius: 12px; padding: 4px 12px; font-size: 11px; color: #5A6572; min-height: 20px; font-weight: 500; } "
                    "QPushButton:hover { background: rgba(0, 122, 255, 0.12); border-color: #007AFF; color: #007AFF; }"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.08); "
                    "border-radius: 12px; padding: 4px 12px; font-size: 11px; color: #8B949E; min-height: 20px; font-weight: 500; } "
                    "QPushButton:hover { background: rgba(10, 132, 255, 0.15); border-color: #0A84FF; color: #FFFFFF; }"
                )

    def _update_search_style(self) -> None:
        """Apply recessed squircle styling to search input box."""
        cur_theme = self._config.get("theme", "dark").lower()
        if hasattr(self, "_search_input"):
            if cur_theme == "light":
                self._search_input.setStyleSheet(
                    "QLineEdit { background-color: #DDE2EB; border: 1px solid #CBD1DC; border-radius: 12px; "
                    "padding: 8px 14px; font-size: 13px; color: #1C2024; font-family: '-apple-system', 'Segoe UI', sans-serif; } "
                    "QLineEdit:focus { border: 1px solid #007AFF; background-color: #ECEFF4; }"
                )
            else:
                self._search_input.setStyleSheet(
                    "QLineEdit { background-color: #0E1218; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; "
                    "padding: 8px 14px; font-size: 13px; color: #E6EDF3; font-family: '-apple-system', 'Segoe UI', sans-serif; } "
                    "QLineEdit:focus { border: 1px solid #0A84FF; background-color: #141820; }"
                )

    def _filter_tools(self) -> None:
        """Filter the action cards based on active category and search query."""
        if not hasattr(self, "_tools_grid") or not hasattr(self, "_search_input"):
            return

        query = self._search_input.text().strip().lower()
        selected_cat = getattr(self, "_active_category", "All")

        visible_actions = []
        for item in MAIN_ACTIONS:
            action_id = item[0]
            icon = item[1]
            label = item[2]
            desc = item[3]
            category = item[4] if len(item) > 4 else "Device"
            tags = item[5] if len(item) > 5 else []

            # 1. Category match
            if selected_cat != "All" and category != selected_cat:
                continue

            # 2. Search query match
            if query:
                text_match = (
                    query in action_id.lower()
                    or query in label.lower()
                    or query in desc.lower()
                    or query in category.lower()
                    or any(query in tag.lower() for tag in tags)
                )
                if not text_match:
                    continue

            visible_actions.append(action_id)

        # 3. Sort visible actions (User Request: "in all tools sort them also")
        sort_mode = self._sort_combo.currentData() if hasattr(self, "_sort_combo") else "recommended"
        action_map = {item[0]: item for item in MAIN_ACTIONS}

        if sort_mode == "az":
            visible_actions.sort(key=lambda aid: action_map[aid][2].lower())
        elif sort_mode == "za":
            visible_actions.sort(key=lambda aid: action_map[aid][2].lower(), reverse=True)
        elif sort_mode == "category":
            visible_actions.sort(key=lambda aid: (action_map[aid][4].lower(), action_map[aid][2].lower()))
        # "recommended" preserves the default curated workflow order in MAIN_ACTIONS

        # Clear items from grid layout (without deleting widgets)
        while self._tools_grid.count():
            self._tools_grid.takeAt(0)

        for act_id, btn in self._action_buttons.items():
            if act_id in visible_actions:
                btn.setVisible(True)
            else:
                btn.setVisible(False)

        cols = 3
        for idx, act_id in enumerate(visible_actions):
            btn = self._action_buttons[act_id]
            r = idx // cols
            c = idx % cols
            self._tools_grid.addWidget(btn, r, c)

        # Fill trailing cells in the last row so buttons maintain uniform width
        remainder = len(visible_actions) % cols
        if remainder:
            for c in range(remainder, cols):
                spacer = QWidget()
                spacer.setStyleSheet("background: transparent;")
                self._tools_grid.addWidget(spacer, len(visible_actions) // cols, c)

        # Empty state & counter handling
        count = len(visible_actions)
        total = len(MAIN_ACTIONS)
        if count == total and not query and selected_cat == "All":
            self._tools_count_badge.setText(f"{total} tools available")
        else:
            self._tools_count_badge.setText(f"Showing {count} of {total} tools")

        if count == 0:
            self._empty_state_widget.setVisible(True)
            self._empty_state_msg.setText(
                f"No tools found matching '{query}'.\n"
                "Try searching for 'root', 'flash', 'bootloop', or click reset."
            )
        else:
            self._empty_state_widget.setVisible(False)

    def _on_search_return_pressed(self) -> None:
        """If exactly one tool is shown, launch it immediately upon Enter."""
        query = self._search_input.text().strip().lower()
        if not query:
            return
        visible_act_ids = [act_id for act_id, btn in self._action_buttons.items() if not btn.isHidden()]
        if len(visible_act_ids) == 1:
            self._on_action(visible_act_ids[0])

    def _reset_filters(self) -> None:
        """Reset search, sort and category filter back to default."""
        self._search_input.clear()
        if hasattr(self, "_sort_combo"):
            self._sort_combo.blockSignals(True)
            self._sort_combo.setCurrentIndex(0)
            self._sort_combo.blockSignals(False)
        self._active_category = "All"
        self._update_category_buttons_style()
        self._filter_tools()

    # ==================================================================
    # Signal wiring
    # ==================================================================

    def _connect_signals(self) -> None:
        # Network monitor -> status bar (thread-safe via invokeMethod)
        def _on_net_change(is_online: bool) -> None:
            QMetaObject.invokeMethod(
                self._status_bar,
                "update_network",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(bool, is_online),
            )
            # Update online/offline button shading (User Addition 1)
            QTimer.singleShot(0, lambda: self._update_network_buttons(is_online))

        self._network.on_change = _on_net_change

        # Wire logger to Side Terminal (User Addition 4)
        terminal_handler = SideTerminalHandler(self._side_terminal.append_line)
        self._side_terminal.set_handler(terminal_handler)
        logging.getLogger("flashdock").addHandler(terminal_handler)

        # Device manager -> UI (thread-safe via QTimer.singleShot)
        def _on_device_changed(info: Optional[DeviceInfo]) -> None:
            # Marshal to the main thread
            QTimer.singleShot(0, lambda: self._handle_device_change(info))

        self._device_mgr.on_device_changed = _on_device_changed

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
        self._status_bar.update_connection_badge(mode, ident, details)
        self._phone_panel.set_mode(mode)
        self._side_terminal.append_colored_stream(
            "INFO", f"Device connected: {details.get('display_name', mode)} [{ident}]"
        )
        if mode in ("mtk_brom", "qualcomm_edl", "unisoc_sprd"):
            self._side_terminal.append_colored_stream(
                "WARN", f"Emergency interface active: {mode.upper()} port ({ident})"
            )
            # Auto-highlight matching tab
            if mode == "mtk_brom" and "mtk_brom" in self._gsm_btn_group:
                self._gsm_btn_group["mtk_brom"].setChecked(True)
            elif mode == "qualcomm_edl" and "qualcomm_edl" in self._gsm_btn_group:
                self._gsm_btn_group["qualcomm_edl"].setChecked(True)
            elif mode == "unisoc_sprd" and "unisoc_sprd" in self._gsm_btn_group:
                self._gsm_btn_group["unisoc_sprd"].setChecked(True)

    @Slot()
    def _on_hardware_device_disconnected(self) -> None:
        """Handle hardware disconnection from background monitor worker."""
        self._status_bar.update_connection_badge("disconnected", "")
        self._side_terminal.append_colored_stream("WARN", "Device disconnected from USB/COM bus.")

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

    @Slot()
    def _handle_device_change(self, info: Optional[DeviceInfo]) -> None:
        """Called on the main thread when the device state changes."""
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

            # Auto-highlight top GSM Suite brand or chipset
            brand_norm = (getattr(info, "brand_normalized", None) or info.brand or "").lower()
            chip_norm = (info.chipset_family or "").lower()
            mode_norm = (info.mode or "").lower()

            target_key = "universal"
            if "xiaomi" in brand_norm or "poco" in brand_norm or "redmi" in brand_norm:
                target_key = "xiaomi"
            elif "samsung" in brand_norm:
                target_key = "samsung"
            elif any(t in brand_norm for t in ("tecno", "infinix", "itel", "transsion")):
                target_key = "transsion"
            elif mode_norm == "brom" or "mediatek" in chip_norm or "mtk" in chip_norm:
                target_key = "mtk_brom"
            elif mode_norm == "edl" or "qualcomm" in chip_norm or "snapdragon" in chip_norm:
                target_key = "qualcomm_edl"
            elif "unisoc" in chip_norm or "spreadtrum" in chip_norm or "sprd" in chip_norm:
                target_key = "unisoc_sprd"

            for k, btn in self._gsm_btn_group.items():
                btn.setChecked(k == target_key)

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
        else:
            self._status_bar.update_device("not_connected", "")
            self._phone_panel.set_mode("not_connected")
            self._phone_panel.set_summary("Connect a phone via USB")
            self._phone_panel.enable_buttons([])
            self._device_selector.update_devices([], None)
            for btn in self._gsm_btn_group.values():
                btn.setChecked(False)


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
            "<p style='color:#8b949e;'>For your own devices only.<br>"
            "Test on a spare phone before using on your main device.</p>",
        )

    @Slot()
    def _show_guide(self) -> None:
        """Open the interactive workflow and function guide (User Addition 7)."""
        dlg = WorkflowGuideDialog(self)
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
        dlg = HardwareKeyGuideDialog(adb=self._adb, parent=self)
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
            self._adb.shell(["input", "keyevent", str(keycode)], serial=self._device_mgr.device.serial)
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
            app.setStyleSheet(get_stylesheet(theme_name))
        if hasattr(self, "_theme_btn"):
            self._theme_btn.setText(self._theme_btn_text(theme_name))
            self._theme_btn.setIcon(get_icon("moon" if theme_name.lower() == "light" else "sun", 14))

        # Update action cards and filter widgets
        for btn in self._action_buttons.values():
            if isinstance(btn, ActionCardButton):
                btn.apply_theme(theme_name)
        if hasattr(self, "_cat_buttons"):
            self._update_category_buttons_style()
        if hasattr(self, "_quick_buttons"):
            self._update_quick_buttons_style()
        if hasattr(self, "_search_input"):
            self._update_search_style()
        if hasattr(self, "_seg_frame"):
            self._update_gsm_segments_style()
        if hasattr(self, "_phone_panel"):
            self._phone_panel.apply_theme(theme_name)
        if hasattr(self, "_live_hud"):
            self._live_hud.apply_theme(theme_name)

        self._update_network_buttons(self._network.is_online)
        log.info("Theme switched to: %s", theme_name)

    def _theme_btn_text(self, theme: str) -> str:
        return "Dark Mode" if theme.lower() == "light" else "Light Mode"

    @Slot(bool)
    def _update_network_buttons(self, is_online: bool) -> None:
        """Shade or disable buttons requiring internet connection when offline (User Addition 1)."""
        online_actions = {"downloads", "integrity"}
        cur_theme = self._config.get("theme", "dark").lower()
        for act_id in online_actions:
            btn = self._action_buttons.get(act_id)
            if not btn:
                continue
            if isinstance(btn, ActionCardButton):
                btn.set_offline_state(not is_online, cur_theme)
            else:
                if is_online:
                    btn.setEnabled(True)
                    btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    desc = self._action_descs.get(act_id, "")
                    btn.setToolTip(desc)
                    btn.setStyleSheet("")
                else:
                    btn.setEnabled(False)
                    btn.setCursor(Qt.CursorShape.ForbiddenCursor)
                    btn.setToolTip("[OFFLINE] Internet connection required for this function.")
                    if cur_theme == "light":
                        btn.setStyleSheet(
                            "QPushButton {"
                            "  background-color: #f4f4f5; border: 1px dashed #d4d4d8;"
                            "  border-radius: 6px; padding: 12px 16px; font-size: 13px;"
                            "  font-weight: 500; text-align: left; color: #a1a1aa;"
                            "}"
                        )
                    else:
                        btn.setStyleSheet(
                            "QPushButton {"
                            "  background-color: #09090b; border: 1px dashed #1f1f23;"
                            "  border-radius: 6px; padding: 12px 16px; font-size: 13px;"
                            "  font-weight: 500; text-align: left; color: #3f3f46;"
                            "}"
                        )

    def _mode_display_text(self) -> str:
        mode = self._config.get("app_mode", "simple").capitalize()
        if self._config.dry_run:
            return f"{mode} mode -- DRY RUN"
        return f"{mode} mode"

    # ==================================================================
    # Window lifecycle
    # ==================================================================

    def showEvent(self, event) -> None:  # noqa: N802
        """Handle window show event: start non-blocking hardware polling."""
        super().showEvent(event)
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
        self._device_mgr.stop()
        self._network.stop()
        log.info("MainWindow closed -- geometry saved.")
        event.accept()
