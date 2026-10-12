"""
FlashDock — Phone Hardware Button & Navigation Guide Modal Dialog.

Provides clear instructions and visual cards for using physical hardware keys
(Vol+, Vol-, Power) to navigate Bootloader, Recovery, FastbootD, EDL, and
Download modes, plus virtual keypad controls when connected via ADB.
"""

from __future__ import annotations

import subprocess
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.ui.icon_assets import create_icon_label, get_icon

log = get_logger(__name__)


class HardwareKeyGuideDialog(QDialog):
    """Interactive hardware key navigation guide and virtual keypad."""

    def __init__(self, adb: Optional[ADB] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Phone Hardware Keys & Navigation Guide")
        self.setWindowIcon(get_icon("phone", 16))
        self.resize(740, 600)
        self.setMinimumSize(620, 480)
        self.setStyleSheet("background-color: #0F141C; color: #E6EDF3;")
        self._adb = adb

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header
        header = QVBoxLayout()
        header.setSpacing(4)
        title_box = QHBoxLayout()
        title_box.setSpacing(8)
        phone_icon = create_icon_label("phone", 22)
        title_box.addWidget(phone_icon)
        title = QLabel("Phone Hardware Keys & Menu Control Guide")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #FFFFFF;")
        title_box.addWidget(title)
        title_box.addStretch()
        header.addLayout(title_box)

        subtitle = QLabel(
            "How to use Volume Up, Volume Down, and Power buttons to navigate device boot menus, "
            "trigger rescue modes, and confirm flashing operations."
        )
        subtitle.setStyleSheet("font-size: 13px; color: #8B949E;")
        subtitle.setWordWrap(True)
        header.addWidget(subtitle)
        layout.addLayout(header)

        # Tabs: 1. Menu Navigation, 2. Brand Key Combos, 3. Virtual Remote Keypad
        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; background: #131822; padding: 12px; } "
            "QTabBar::tab { padding: 8px 18px; font-weight: 600; font-size: 13px; color: #8B949E; background: transparent; } "
            "QTabBar::tab:selected { color: #0A84FF; border-bottom: 2px solid #0A84FF; } "
            "QTabBar::tab:hover { color: #E6EDF3; }"
        )

        tab_nav = QWidget()
        self._setup_nav_tab(tab_nav)
        tabs.addTab(tab_nav, "Bootloader Navigation")
        tabs.setTabIcon(0, get_icon("tools", 14))

        tab_combos = QWidget()
        self._setup_combos_tab(tab_combos)
        tabs.addTab(tab_combos, "Brand Key Combos")
        tabs.setTabIcon(1, get_icon("flash", 14))

        tab_remote = QWidget()
        self._setup_remote_tab(tab_remote)
        tabs.addTab(tab_remote, "Virtual Keypad (ADB)")
        tabs.setTabIcon(2, get_icon("phone", 14))

        layout.addWidget(tabs, 1)

        # Footer
        footer = QHBoxLayout()
        footer.addStretch()
        btn_close = QPushButton("Done")
        btn_close.setStyleSheet(
            "QPushButton { background: #0A84FF; color: #FFFFFF; border: none; border-radius: 8px; padding: 8px 24px; font-weight: 600; } "
            "QPushButton:hover { background: #0070E0; }"
        )
        btn_close.clicked.connect(self.accept)
        footer.addWidget(btn_close)
        layout.addLayout(footer)

    def _setup_nav_tab(self, parent: QWidget) -> None:
        scroll = QScrollArea(parent)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setSpacing(12)

        # Core Rule Banner Card
        rule_card = QFrame()
        rule_card.setStyleSheet(
            "background: rgba(10, 132, 255, 0.12); border: 1px solid rgba(10, 132, 255, 0.3); border-radius: 10px; padding: 14px;"
        )
        r_lay = QVBoxLayout(rule_card)
        r_lay.setSpacing(6)
        r_title = QLabel("Universal Android Boot Menu Rule")
        r_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #0A84FF;")
        r_desc = QLabel(
            "When your phone is in Fastboot, Bootloader, or Recovery mode, the touch screen is usually disabled. "
            "You MUST use the physical hardware buttons on the side of your phone to control the menu:"
        )
        r_desc.setStyleSheet("font-size: 13px; color: #E6EDF3;")
        r_desc.setWordWrap(True)
        r_lay.addWidget(r_title)
        r_lay.addWidget(r_desc)
        lay.addWidget(rule_card)

        # 3 Key Cards
        keys = [
            ("Volume Up", "#10B981", "Scroll UP / Previous Item", "Moves the on-screen selection cursor UP. On some unlock screens, holding Volume Up confirms the bootloader unlock request."),
            ("Volume Down", "#3B82F6", "Scroll DOWN / Next Item", "Moves the on-screen selection cursor DOWN through options like 'Recovery mode', 'Restart bootloader', and 'Power off'."),
            ("Power Button", "#EF4444", "SELECT / Enter / Confirm", "Acts as the 'ENTER' key. Press once to execute whichever menu option is currently highlighted on your phone screen."),
        ]

        for k_name, k_color, k_action, k_desc in keys:
            card = QFrame()
            card.setStyleSheet(
                f"background: #181E26; border: 1px solid rgba(255, 255, 255, 0.08); "
                f"border-left-width: 5px; border-left-color: {k_color}; border-radius: 8px; padding: 12px;"
            )
            c_lay = QVBoxLayout(card)
            c_lay.setSpacing(4)
            h = QHBoxLayout()
            lbl_name = QLabel(k_name)
            lbl_name.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {k_color};")
            lbl_action = QLabel(f"➔  <b>{k_action}</b>")
            lbl_action.setStyleSheet("font-size: 13px; color: #E6EDF3;")
            h.addWidget(lbl_name)
            h.addWidget(lbl_action)
            h.addStretch()
            c_lay.addLayout(h)

            lbl_desc = QLabel(k_desc)
            lbl_desc.setStyleSheet("font-size: 12px; color: #8B949E;")
            lbl_desc.setWordWrap(True)
            c_lay.addWidget(lbl_desc)
            lay.addWidget(card)

        lay.addStretch()
        scroll.setWidget(container)
        p_lay = QVBoxLayout(parent)
        p_lay.setContentsMargins(0, 0, 0, 0)
        p_lay.addWidget(scroll)

    def _setup_combos_tab(self, parent: QWidget) -> None:
        scroll = QScrollArea(parent)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setSpacing(10)

        combos = [
            ("Google Pixel", "Power + Volume Down", "Fastboot Mode", "Turn off phone. Hold both buttons together until the Fastboot logo appears."),
            ("Google Pixel", "Power + Volume Up (after Fastboot)", "Stock Recovery", "In Fastboot, select 'Recovery Mode' with Vol keys and press Power."),
            ("Xiaomi / Poco / Redmi", "Power + Volume Down", "Fastboot (FASTBOOT rabbit)", "Power off. Hold Power + Vol Down until orange 'FASTBOOT' text appears."),
            ("Xiaomi / Poco / Redmi", "Power + Volume Up", "Mi Recovery / Assistant", "Power off. Hold Power + Vol Up until Mi logo appears, then release Power."),
            ("Samsung Galaxy", "Volume Down + Volume Up + Plug USB", "Download / Odin Mode", "Turn off phone. Hold Vol Down + Vol Up together, then connect USB cable from PC."),
            ("Samsung Galaxy", "Power + Volume Up + Plug USB", "Recovery Mode", "Connect USB cable to PC. Hold Power + Vol Up until Samsung logo appears."),
            ("OnePlus / Realme", "Power + Volume Down", "Fastboot Mode", "Turn off phone. Hold Power + Vol Down until OnePlus logo / Fastboot appears."),
            ("Qualcomm EDL 9008", "Volume Up + Volume Down + Plug USB", "Emergency Download (EDL)", "Hold both Vol keys on hard-bricked phone while connecting USB cable."),
            ("MediaTek BROM", "Volume Down (or Vol Up) + Plug USB", "BootROM (BROM)", "Power off phone. Hold Vol Down while plugging in USB cable to trigger MTK BROM handshake."),
        ]

        for brand, keys, target, notes in combos:
            card = QFrame()
            card.setStyleSheet(
                "background: #181E26; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 10px;"
            )
            c_lay = QVBoxLayout(card)
            c_lay.setSpacing(4)

            top = QHBoxLayout()
            b_lbl = QLabel(f"<b>{brand}</b>")
            b_lbl.setStyleSheet("font-size: 13px; color: #E6EDF3;")
            t_lbl = QLabel(f"→  <span style='color:#30D158; font-weight:700;'>{target}</span>")
            t_lbl.setStyleSheet("font-size: 13px;")
            top.addWidget(b_lbl)
            top.addWidget(t_lbl)
            top.addStretch()
            c_lay.addLayout(top)

            k_lbl = QLabel(f"<b>Keys:</b> <code style='background:rgba(255, 255, 255, 0.08); color:#0A84FF; padding:2px 6px; border-radius:4px;'>{keys}</code>")
            k_lbl.setStyleSheet("font-size: 12px; color: #E6EDF3;")
            c_lay.addWidget(k_lbl)

            n_lbl = QLabel(notes)
            n_lbl.setStyleSheet("font-size: 11px; color: #8B949E;")
            n_lbl.setWordWrap(True)
            c_lay.addWidget(n_lbl)

            lay.addWidget(card)

        lay.addStretch()
        scroll.setWidget(container)
        p_lay = QVBoxLayout(parent)
        p_lay.setContentsMargins(0, 0, 0, 0)
        p_lay.addWidget(scroll)

    def _setup_remote_tab(self, parent: QWidget) -> None:
        lay = QVBoxLayout(parent)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(14)

        desc = QLabel(
            "Send virtual hardware keypresses directly to your connected Android phone via ADB "
            "(<code>adb shell input keyevent</code>). Works when the phone is booted with USB debugging."
        )
        desc.setStyleSheet("font-size: 13px; color: #8B949E;")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        keypad_frame = QFrame()
        keypad_frame.setStyleSheet(
            "background: #181E26; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 16px;"
        )
        grid = QGridLayout(keypad_frame)
        grid.setSpacing(10)

        buttons = [
            ("Volume +", 24, "audio", 0, 0),
            ("Volume -", 25, "audio", 0, 1),
            ("Power", 26, "power", 0, 2),
            ("D-Pad Up", 19, "tools", 1, 0),
            ("Enter / Select", 66, "check", 1, 1),
            ("D-Pad Down", 20, "tools", 1, 2),
            ("Back", 4, "return_stock", 2, 0),
            ("Home", 3, "home", 2, 1),
            ("Recent Apps", 187, "modules", 2, 2),
        ]

        for label, keycode, ico, r, c in buttons:
            btn = QPushButton(label)
            btn.setIcon(get_icon(ico, 14))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(44)
            btn.setStyleSheet(
                "QPushButton { background: #212836; border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 8px; "
                "font-weight: 600; font-size: 13px; color: #E6EDF3; } "
                "QPushButton:hover { background: #2D3748; border-color: #0A84FF; color: #0A84FF; } "
                "QPushButton:pressed { background: #1A202C; }"
            )
            btn.clicked.connect(lambda _, code=keycode: self._send_keyevent(code))
            grid.addWidget(btn, r, c)

        lay.addWidget(keypad_frame)

        self._status_lbl = QLabel("Ready. Click any button above to send keyevent.")
        self._status_lbl.setStyleSheet("font-size: 12px; color: #8B949E; font-style: italic;")
        lay.addWidget(self._status_lbl)
        lay.addStretch()

    def _send_keyevent(self, keycode: int) -> None:
        """Sends adb shell input keyevent <keycode>."""
        if not self._adb or not self._adb.available:
            self._status_lbl.setText("ADB binary not available.")
            self._status_lbl.setStyleSheet("font-size: 12px; color: #DC2626;")
            return

        try:
            res = self._adb.shell(["input", "keyevent", str(keycode)])
            if res.success:
                self._status_lbl.setText(f"Sent keyevent {keycode} successfully.")
                self._status_lbl.setStyleSheet("font-size: 12px; color: #059669;")
            else:
                self._status_lbl.setText(f"Failed to send keyevent: {res.stderr or 'device error'}")
                self._status_lbl.setStyleSheet("font-size: 12px; color: #D97706;")
        except Exception as e:
            self._status_lbl.setText(f"Error: {e}")
            self._status_lbl.setStyleSheet("font-size: 12px; color: #DC2626;")
