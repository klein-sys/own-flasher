"""
FlashDock — Phone Control Panel (sidebar widget).

Always visible in the main window. Merges Xiaomi HyperOS 2.0 fluidity,
macOS Sequoia glassmorphism, and iOS 18 Control Center aesthetics:
- Prominent vertical pill navigation with 32x32px vibrant circular badges.
- Smooth active capsule selection (mirroring AFS / Apple HIG standard).
- Collapsible device mode monitor, quick reboot triggers, and setup assistant.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from flashdock.logger import get_logger
from flashdock.ui.icon_assets import create_icon_label, get_icon, get_icon_pixmap

log = get_logger(__name__)


class _ModeIndicator(QFrame):
    """Coloured pill that shows the phone's current mode."""

    _COLORS = {
        "system":       ("#34C759", "System"),
        "recovery":     ("#FF9500", "Recovery"),
        "bootloader":   ("#007AFF", "Bootloader"),
        "fastbootd":    ("#007AFF", "FastbootD"),
        "download":     ("#AF52DE", "Download"),
        "edl":          ("#FF3B30", "EDL"),
        "brom":         ("#FF3B30", "BROM"),
        "sideload":     ("#FF9500", "Sideload"),
        "unauthorized": ("#FF9500", "Unauthorized"),
        "offline":      ("#8E8E93", "Offline"),
        "not_connected":("#8E8E93", "Not connected"),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._dot = QLabel()
        self._dot.setFixedSize(8, 8)
        self._text = QLabel("Not connected")
        self._text.setProperty("cssClass", "metric")
        self._layout.addWidget(self._dot)
        self._layout.addWidget(self._text)
        self._layout.addStretch()
        self.set_mode("not_connected")

    def set_mode(self, mode: str) -> None:
        color, label = self._COLORS.get(mode, ("#8E8E93", mode.title()))
        self._dot.setStyleSheet(
            f"background-color: {color}; border-radius: 4px; "
            "min-width: 8px; max-width: 8px; "
            "min-height: 8px; max-height: 8px;"
        )
        self._text.setText(label)
        self._text.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 600;")


class _NavPillButton(QPushButton):
    """Next-Gen HyperOS / iOS 18 Control Center Primary Navigation Pill.

    Houses a 32x32px circular chip container with vivid gradient and antialiased
    white vector SVG icon, bold label, and responsive active capsule highlight.
    """

    def __init__(
        self,
        action_id: str,
        label: str,
        icon_name: str,
        gradient_css: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.action_id = action_id
        self.label_str = label
        self.icon_name = icon_name
        self.gradient_css = gradient_css
        self.is_active = False

        self.setProperty("cssClass", "nav_pill")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 10, 4)
        layout.setSpacing(10)

        # Circular Chip Container (28x28px, radius 14px)
        self.chip = QFrame()
        self.chip.setFixedSize(28, 28)
        self.chip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.chip.setStyleSheet(f"background: {self.gradient_css}; border-radius: 14px; border: none;")

        chip_lay = QHBoxLayout(self.chip)
        chip_lay.setContentsMargins(0, 0, 0, 0)
        chip_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(14, 14)
        self.icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        pix = get_icon_pixmap(self.icon_name, width=14, height=14, color="#FFFFFF")
        self.icon_lbl.setPixmap(pix)
        chip_lay.addWidget(self.icon_lbl)
        layout.addWidget(self.chip, 0, Qt.AlignmentFlag.AlignVCenter)

        # Title Label
        self.title_lbl = QLabel(label)
        self.title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.title_lbl, 1)

    def set_active(self, active: bool, theme: str = "dark") -> None:
        self.is_active = active
        self.setProperty("active", "true" if active else "false")
        theme = theme.lower()

        if active:
            if theme == "light":
                self.setStyleSheet("""
                    QPushButton {
                        background-color: #9AA2B0;
                        border: 1px solid #828B9B;
                        border-radius: 12px;
                        color: #FFFFFF;
                        font-weight: 700;
                    }
                """)
                self.title_lbl.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: 700; background: transparent;")
            else:
                self.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #253346, stop:1 #1C2736);
                        border: 1px solid #0A84FF;
                        border-radius: 12px;
                        color: #FFFFFF;
                        font-weight: 700;
                    }
                """)
                self.title_lbl.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: 700; background: transparent;")
        else:
            if theme == "light":
                self.setStyleSheet("""
                    QPushButton {
                        background-color: #E2E6EC;
                        border: 1px solid #CBD1DC;
                        border-radius: 12px;
                        color: #1C2024;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background-color: #ECEFF4;
                        border-color: #9AA4B2;
                        color: #1C2024;
                    }
                """)
                self.title_lbl.setStyleSheet("color: #1C2024; font-size: 12px; font-weight: 600; background: transparent;")
            else:
                self.setStyleSheet("""
                    QPushButton {
                        background-color: #161D28;
                        border: 1px solid rgba(255, 255, 255, 0.07);
                        border-radius: 12px;
                        color: #E6EDF3;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background-color: #1E2736;
                        border-color: #3D4B5C;
                        color: #FFFFFF;
                    }
                """)
                self.title_lbl.setStyleSheet("color: #E6EDF3; font-size: 12px; font-weight: 600; background: transparent;")


class PhoneControlPanel(QFrame):
    """Sidebar workstation control and navigation panel."""

    reboot_requested = Signal(str)
    refresh_requested = Signal()
    scrcpy_requested = Signal()
    key_event_requested = Signal(int)
    key_guide_requested = Signal()
    setup_wizard_requested = Signal()
    restart_adb_requested = Signal()
    action_requested = Signal(str)
    switchboard_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(240)
        self.setProperty("cssClass", "operations_panel")

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 14, 10, 14)
        root.setSpacing(6)

        # ---- Top Header Brand Pill ----
        brand_frame = QFrame()
        brand_frame.setFixedHeight(54)
        brand_frame.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 18px;
            }
        """)
        brand_lay = QHBoxLayout(brand_frame)
        brand_lay.setContentsMargins(10, 8, 12, 8)
        brand_lay.setSpacing(10)

        # Brand squircle icon chip
        brand_icon_chip = QFrame()
        brand_icon_chip.setFixedSize(34, 34)
        brand_icon_chip.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00F2FE, stop:1 #4FACFE);
            border-radius: 10px;
            border: none;
        """)
        b_chip_lay = QHBoxLayout(brand_icon_chip)
        b_chip_lay.setContentsMargins(0, 0, 0, 0)
        b_chip_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b_logo_lbl = QLabel()
        b_logo_lbl.setPixmap(get_icon_pixmap("app_logo", width=20, height=20, color="#FFFFFF"))
        b_chip_lay.addWidget(b_logo_lbl)
        brand_lay.addWidget(brand_icon_chip)

        brand_text_box = QVBoxLayout()
        brand_text_box.setSpacing(1)
        brand_title = QLabel("FlashDock")
        brand_title.setStyleSheet("font-size: 14px; font-weight: 700; letter-spacing: -0.3px;")
        brand_sub = QLabel("v1.2.0 Service Suite")
        brand_sub.setStyleSheet("font-size: 11px; color: #8E8E93;")
        brand_text_box.addWidget(brand_title)
        brand_text_box.addWidget(brand_sub)
        brand_lay.addLayout(brand_text_box, 1)
        root.addWidget(brand_frame)

        # ---- Primary Navigation Pills wrapped in sleek QScrollArea (Section 3.2) ----
        nav_scroll = QScrollArea()
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: transparent;
                width: 4px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(142, 142, 147, 0.3);
                border-radius: 2px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(142, 142, 147, 0.6);
            }
        """)

        nav_container = QWidget()
        nav_container.setStyleSheet("background: transparent;")
        nav_lay = QVBoxLayout(nav_container)
        nav_lay.setContentsMargins(0, 0, 0, 0)
        nav_lay.setSpacing(4)

        self._nav_pills: dict[str, _NavPillButton] = {}
        nav_defs = [
            ("home",         "Overview / Tools",    "flash",       "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00E5FF, stop:1 #0097A7)"),
            ("check_phone",  "ADB & Device",        "phone",       "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00B4D8, stop:1 #0077B6)"),
            ("flash_rom",    "Fastboot Tools",      "flash",       "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2563EB, stop:1 #1D4ED8)"),
            ("root",         "Root & Modules",      "root",        "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #A855F7, stop:1 #7E22CE)"),
            ("unbrick",      "Unbrick & Rescue",    "unbrick",     "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EF4444, stop:1 #B91C1C)"),
            ("diagnostics",  "Diagnostics & Tweaks","diagnostics", "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #10B981, stop:1 #059669)"),
            ("mtk_unisoc",   "MTK & Unisoc",        "mtk_unisoc",  "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F97316, stop:1 #C2410C)"),
            ("settings",     "Display & Settings",  "tools",       "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EC4899, stop:1 #BE185D)"),
            ("about",        "About Workstation",   "info",        "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EA580C, stop:1 #9A3412)"),
        ]

        for action_id, label, icon_name, grad in nav_defs:
            pill = _NavPillButton(action_id, label, icon_name, grad)
            pill.clicked.connect(lambda checked=False, a=action_id: self._on_nav_pill_clicked(a))
            self._nav_pills[action_id] = pill
            nav_lay.addWidget(pill)

        nav_lay.addStretch(1)
        nav_scroll.setWidget(nav_container)
        root.addWidget(nav_scroll, 1)

        # Set Home active initially
        self._active_nav_id = "home"
        self._nav_pills["home"].set_active(True)

        # ---- Collapsible Bottom Device Status Capsule ----
        dev_card = QFrame()
        dev_card.setStyleSheet("""
            QFrame {
                background: rgba(0, 0, 0, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 14px;
                padding: 6px;
            }
        """)
        dev_lay = QVBoxLayout(dev_card)
        dev_lay.setContentsMargins(8, 8, 8, 8)
        dev_lay.setSpacing(6)

        # Mode indicator row
        self._mode = _ModeIndicator()
        dev_lay.addWidget(self._mode)

        self._summary = QLabel("Connect a phone via USB")
        self._summary.setWordWrap(True)
        self._summary.setProperty("cssClass", "muted")
        self._summary.setStyleSheet("font-size: 11px;")
        dev_lay.addWidget(self._summary)

        # Quick Reboot Actions
        reboot_row = QHBoxLayout()
        reboot_row.setSpacing(4)

        self._buttons: dict[str, QPushButton] = {}
        button_defs = [
            ("system",     "System",      "refresh",    "Reboot into Android"),
            ("recovery",   "Recovery",    "tools",      "Reboot to Recovery mode"),
            ("bootloader", "Fastboot",    "flash",      "Reboot to Bootloader / Fastboot"),
            ("fastbootd",  "FastbootD",   "flash",      "Reboot to userspace Fastboot"),
            ("download",   "Odin",        "downloads",  "Samsung Download mode"),
            ("edl",        "EDL",         "usb",        "Qualcomm EDL / 9008 mode"),
            ("poweroff",   "Power Off",   "power",      "Power off the device"),
            ("safemode",   "Safe Mode",   "integrity",  "Reboot into Safe Mode"),
        ]

        # Primary 3 visible reboot shortcuts in pill drawer
        for mode_id, label, icon_name, tooltip in button_defs[:3]:
            btn = QPushButton(label)
            btn.setIcon(get_icon(icon_name, 11))
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("font-size: 10px; padding: 4px 6px; border-radius: 8px;")
            btn.setEnabled(False)
            btn.clicked.connect(lambda checked, m=mode_id: self.reboot_requested.emit(m))
            self._buttons[mode_id] = btn
            reboot_row.addWidget(btn)

        # Dedicated "More / Switchboard" button
        self._btn_more_reboot = QPushButton("More...")
        self._btn_more_reboot.setIcon(get_icon("tools", 11))
        self._btn_more_reboot.setToolTip("Open Multi-Mode Power & Reboot Switchboard (EDL, Odin, FastbootD, Power Off)")
        self._btn_more_reboot.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_more_reboot.setStyleSheet("font-size: 10px; padding: 4px 6px; border-radius: 8px; color: #007AFF; font-weight: 600;")
        self._btn_more_reboot.clicked.connect(self.switchboard_requested.emit)
        reboot_row.addWidget(self._btn_more_reboot)

        dev_lay.addLayout(reboot_row)

        # Store other buttons hidden for API and backward compatibility
        for mode_id, label, icon_name, tooltip in button_defs[3:]:
            btn = QPushButton(label)
            btn.setVisible(False)
            btn.setEnabled(False)
            btn.clicked.connect(lambda checked, m=mode_id: self.reboot_requested.emit(m))
            self._buttons[mode_id] = btn

        # Connection Helper Card
        self._helper_card = QFrame()
        self._helper_card.setStyleSheet(
            "background-color: rgba(255, 149, 0, 0.08); border: 1px solid rgba(255, 149, 0, 0.25); "
            "border-radius: 8px; padding: 6px;"
        )
        helper_lay = QVBoxLayout(self._helper_card)
        helper_lay.setContentsMargins(4, 4, 4, 4)
        helper_lay.setSpacing(4)

        helper_title_row = QHBoxLayout()
        helper_title_row.setSpacing(6)
        self._helper_icon = create_icon_label("info", 13, color="#C96E00")
        helper_title_row.addWidget(self._helper_icon)

        self._helper_title = QLabel("Device Offline")
        self._helper_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #C96E00;")
        helper_title_row.addWidget(self._helper_title, 1)
        helper_lay.addLayout(helper_title_row)

        self._helper_text = QLabel("Plug USB cable & enable USB Debugging.")
        self._helper_text.setStyleSheet("font-size: 10px; color: #8E8E93;")
        self._helper_text.setWordWrap(True)
        helper_lay.addWidget(self._helper_text)

        helper_btn_row = QHBoxLayout()
        helper_btn_row.setSpacing(4)

        self._btn_setup_diag = QPushButton("Setup")
        self._btn_setup_diag.setIcon(get_icon("tools", 11))
        self._btn_setup_diag.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_setup_diag.setStyleSheet("font-size: 10px; padding: 3px 6px;")
        self._btn_setup_diag.clicked.connect(self.setup_wizard_requested.emit)
        helper_btn_row.addWidget(self._btn_setup_diag)

        self._btn_rescan = QPushButton("Scan")
        self._btn_rescan.setIcon(get_icon("refresh", 11))
        self._btn_rescan.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_rescan.setStyleSheet("font-size: 10px; padding: 3px 6px;")
        self._btn_rescan.clicked.connect(self._on_rescan_clicked)
        helper_btn_row.addWidget(self._btn_rescan)
        helper_lay.addLayout(helper_btn_row)

        dev_lay.addWidget(self._helper_card)

        # Screen Mirror & Key Guide triggers
        bottom_tools_row = QHBoxLayout()
        bottom_tools_row.setSpacing(4)

        self._mirror_btn = QPushButton("Mirror")
        self._mirror_btn.setIcon(get_icon("scrcpy", 12, color="#FFFFFF"))
        self._mirror_btn.setObjectName("mirror_btn")
        self._mirror_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mirror_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007AFF, stop:1 #5856D6);
                color: #FFFFFF;
                font-weight: 600;
                font-size: 11px;
                border-radius: 8px;
                padding: 4px 8px;
                border: none;
            }
        """)
        self._mirror_btn.clicked.connect(self.scrcpy_requested.emit)
        bottom_tools_row.addWidget(self._mirror_btn)

        btn_guide = QPushButton("Keys")
        btn_guide.setIcon(get_icon("phone", 12))
        btn_guide.setObjectName("btn_key_guide")
        btn_guide.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_guide.setStyleSheet("font-size: 11px; padding: 4px 8px; font-weight: 600; border-radius: 8px;")
        btn_guide.clicked.connect(self.key_guide_requested.emit)
        bottom_tools_row.addWidget(btn_guide)
        dev_lay.addLayout(bottom_tools_row)

        root.addWidget(dev_card)

        # Backward compatibility aliases and programmatic test buttons
        self._btn_op_info = QPushButton(self)
        self._btn_op_info.setVisible(False)
        self._btn_op_info.clicked.connect(lambda: self.action_requested.emit("check_phone"))

        self._btn_op_backup = QPushButton(self)
        self._btn_op_backup.setVisible(False)
        self._btn_op_backup.clicked.connect(lambda: self.action_requested.emit("backup"))

        self._btn_op_flash = QPushButton(self)
        self._btn_op_flash.setVisible(False)
        self._btn_op_flash.clicked.connect(lambda: self.action_requested.emit("flash_rom"))

        self._btn_op_unlock = QPushButton(self)
        self._btn_op_unlock.setVisible(False)
        self._btn_op_unlock.clicked.connect(lambda: self.action_requested.emit("unlock_bl"))

        self._btn_vol_up = QPushButton(self)
        self._btn_vol_up.setObjectName("btn_key_volup")
        self._btn_vol_up.setVisible(False)
        self._btn_vol_up.clicked.connect(lambda: self.key_event_requested.emit(24))

        self._btn_vol_down = QPushButton(self)
        self._btn_vol_down.setObjectName("btn_key_voldown")
        self._btn_vol_down.setVisible(False)
        self._btn_vol_down.clicked.connect(lambda: self.key_event_requested.emit(25))

        self._btn_power = QPushButton(self)
        self._btn_power.setObjectName("btn_key_power")
        self._btn_power.setVisible(False)
        self._btn_power.clicked.connect(lambda: self.key_event_requested.emit(26))

    # ---- Internal Slots ---------------------------------------------------

    def _on_nav_pill_clicked(self, action_id: str) -> None:
        self.set_active_nav(action_id)
        self.action_requested.emit(action_id)

    def _on_rescan_clicked(self) -> None:
        """Trigger device re-scan and restart ADB server if unauthorized."""
        if getattr(self, "_last_mode", "") == "unauthorized":
            self.restart_adb_requested.emit()
        else:
            self.refresh_requested.emit()

    # ---- Public API -------------------------------------------------------

    def set_active_nav(self, action_id: str, theme: str = "dark") -> None:
        """Set the active visual navigation pill."""
        self._active_nav_id = action_id
        for aid, pill in self._nav_pills.items():
            pill.set_active(aid == action_id, theme=theme)

    def apply_theme(self, theme: str) -> None:
        """Re-apply active and inactive styles for all pills on theme change."""
        for aid, pill in self._nav_pills.items():
            pill.set_active(aid == self._active_nav_id, theme=theme)

    def set_mode(self, mode: str) -> None:
        """Update the mode indicator pill and helper guidance card."""
        self._last_mode = mode
        self._mode.set_mode(mode)

        if mode == "not_connected":
            self._helper_card.setVisible(True)
            self._helper_icon.setPixmap(get_icon_pixmap("info", 13, color="#C96E00"))
            self._helper_title.setText("Device Offline")
            self._helper_text.setText("Plug USB cable & enable USB Debugging.")
        elif mode == "unauthorized":
            self._helper_card.setVisible(True)
            self._helper_icon.setPixmap(get_icon_pixmap("warning", 13, color="#FF9500"))
            self._helper_title.setText("Accept RSA Prompt")
            self._helper_text.setText("Tap 'Always allow' on device screen.")
        else:
            self._helper_card.setVisible(False)

    def set_summary(self, text: str) -> None:
        """Update the short device summary text."""
        self._summary.setText(text)

    def enable_buttons(self, allowed: list[str]) -> None:
        """Enable only the buttons whose *mode_id* is in *allowed*."""
        for mode_id, btn in self._buttons.items():
            btn.setEnabled(mode_id in allowed)
            if mode_id not in allowed:
                btn.setToolTip("Not available in current mode")
