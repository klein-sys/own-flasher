"""
FlashDock — Phone Control Panel (sidebar widget).

Always visible in the main window.  Shows the device's current mode and
provides reboot / control buttons.  Buttons that don't apply to the
detected brand or current mode are greyed out with a tooltip reason.

Phase 1 builds the visual shell; Phase 2 connects it to real ADB/fastboot.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flashdock.logger import get_logger

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
        self._text.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 600;")


class PhoneControlPanel(QFrame):
    """Sidebar control panel for the connected phone."""

    reboot_requested = Signal(str)
    refresh_requested = Signal()
    scrcpy_requested = Signal()
    key_event_requested = Signal(int)
    key_guide_requested = Signal()
    setup_wizard_requested = Signal()
    restart_adb_requested = Signal()
    action_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(220)
        self.setProperty("cssClass", "operations_panel")

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 18, 14, 18)
        root.setSpacing(10)

        # ---- Header ----
        header = QLabel("PHONE CONTROL")
        header.setProperty("cssClass", "subheading")
        header.setStyleSheet("font-size: 11px; font-weight: 700; letter-spacing: 0.6px;")
        root.addWidget(header)

        # ---- Mode indicator ----
        self._mode = _ModeIndicator()
        root.addWidget(self._mode)

        # ---- Device summary (brief) ----
        self._summary = QLabel("Connect a phone via USB")
        self._summary.setWordWrap(True)
        self._summary.setProperty("cssClass", "muted")
        root.addWidget(self._summary)

        # ---- Connection Helper & Troubleshooting Card ----
        self._helper_card = QFrame()
        self._helper_card.setStyleSheet(
            "background-color: rgba(255, 149, 0, 0.08); border: 1px solid rgba(255, 149, 0, 0.25); "
            "border-radius: 8px; padding: 8px 10px;"
        )
        helper_lay = QVBoxLayout(self._helper_card)
        helper_lay.setContentsMargins(4, 4, 4, 4)
        helper_lay.setSpacing(6)

        self._helper_title = QLabel("💡 Phone Not Detected?")
        self._helper_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #C96E00;")
        helper_lay.addWidget(self._helper_title)

        self._helper_text = QLabel(
            "1. Settings > About Phone > Tap 'Build Number' 7x.\n"
            "2. Developer options > Turn ON 'USB Debugging'.\n"
            "3. Accept RSA prompt on screen."
        )
        self._helper_text.setStyleSheet("font-size: 10px; color: #8E8E93; line-height: 1.3;")
        self._helper_text.setWordWrap(True)
        helper_lay.addWidget(self._helper_text)

        helper_btn_row = QHBoxLayout()
        helper_btn_row.setSpacing(4)

        self._btn_setup_diag = QPushButton("🛠️ Setup")
        self._btn_setup_diag.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_setup_diag.setStyleSheet("font-size: 10px; padding: 4px 6px; font-weight: 600;")
        self._btn_setup_diag.setToolTip("Open Laptop Setup Wizard & USB driver installer")
        self._btn_setup_diag.clicked.connect(self.setup_wizard_requested.emit)
        helper_btn_row.addWidget(self._btn_setup_diag)

        self._btn_rescan = QPushButton("🔄 Scan")
        self._btn_rescan.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_rescan.setStyleSheet("font-size: 10px; padding: 4px 6px; font-weight: 600;")
        self._btn_rescan.setToolTip("Re-scan USB devices and restart ADB detection")
        self._btn_rescan.clicked.connect(self._on_rescan_clicked)
        helper_btn_row.addWidget(self._btn_rescan)

        helper_lay.addLayout(helper_btn_row)
        root.addWidget(self._helper_card)

        # ---- Section: GSM Operations Panel ----
        ops_header = QLabel("OPERATIONS")
        ops_header.setProperty("cssClass", "subheading")
        ops_header.setStyleSheet("font-size: 10px; font-weight: 700; letter-spacing: 0.5px; margin-top: 4px; color: #8E8E93;")
        root.addWidget(ops_header)

        self._btn_op_info = QPushButton("🔍  Device Diagnostics")
        self._btn_op_info.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_op_info.setToolTip("Deep device property inspection & root/Knox detection")
        self._btn_op_info.clicked.connect(lambda: self.action_requested.emit("check_phone"))
        root.addWidget(self._btn_op_info)

        self._btn_op_backup = QPushButton("💼  Partition Backup")
        self._btn_op_backup.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_op_backup.setToolTip("Back up calibration blocks (NVRAM, EFS, Persist)")
        self._btn_op_backup.clicked.connect(lambda: self.action_requested.emit("backup"))
        root.addWidget(self._btn_op_backup)

        self._btn_op_flash = QPushButton("⚡  Flash Firmware")
        self._btn_op_flash.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_op_flash.setToolTip("Flash images, fastboot packages, or Treble GSIs")
        self._btn_op_flash.clicked.connect(lambda: self.action_requested.emit("flash_rom"))
        root.addWidget(self._btn_op_flash)

        self._btn_op_unlock = QPushButton("🔓  Bootloader Tools")
        self._btn_op_unlock.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_op_unlock.setToolTip("Brand-aware bootloader unlock / relock wizard")
        self._btn_op_unlock.clicked.connect(lambda: self.action_requested.emit("unlock_bl"))
        root.addWidget(self._btn_op_unlock)

        # ---- Separator ----
        sep = QFrame()
        sep.setProperty("cssClass", "separator")
        root.addWidget(sep)

        # ---- Section: Reboot shortcuts ----
        reboot_header = QLabel("REBOOT SHORTCUTS")
        reboot_header.setProperty("cssClass", "subheading")
        reboot_header.setStyleSheet("font-size: 10px; font-weight: 700; letter-spacing: 0.5px; color: #8E8E93;")
        root.addWidget(reboot_header)

        self._buttons: dict[str, QPushButton] = {}
        button_defs = [
            ("system",     "⟳  Reboot",          "Reboot into Android"),
            ("recovery",   "🔧  Recovery",        "Reboot to Recovery mode"),
            ("bootloader", "⚡  Bootloader",      "Reboot to Bootloader / Fastboot"),
            ("fastbootd",  "⚡  FastbootD",       "Reboot to userspace Fastboot"),
            ("download",   "⬇  Download",         "Samsung Download mode"),
            ("edl",        "🔌  EDL",             "Qualcomm EDL / 9008 mode"),
            ("poweroff",   "⏻  Power off",       "Power off the device"),
            ("safemode",   "🛡  Safe mode",       "Reboot into Safe Mode"),
        ]

        for mode_id, label, tooltip in button_defs:
            btn = QPushButton(label)
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setEnabled(False)
            btn.clicked.connect(lambda checked, m=mode_id: self.reboot_requested.emit(m))
            self._buttons[mode_id] = btn
            root.addWidget(btn)

        # ---- Separator ----
        sep2 = QFrame()
        sep2.setProperty("cssClass", "separator")
        root.addWidget(sep2)

        # ---- Screen mirror (scrcpy) ----
        self._mirror_btn = QPushButton("🖥️  Mirror Screen")
        self._mirror_btn.setObjectName("mirror_btn")
        self._mirror_btn.setToolTip("Open low-latency screen mirror & remote control (scrcpy)")
        self._mirror_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mirror_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007AFF, stop:1 #5856D6);
                color: #FFFFFF;
                font-weight: 600;
                border-radius: 6px;
                padding: 6px 10px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0062CC, stop:1 #4745B8);
            }
        """)
        self._mirror_btn.clicked.connect(self.scrcpy_requested.emit)
        root.addWidget(self._mirror_btn)

        # ---- Hardware Key Navigation Guide Launcher ----
        sep3 = QFrame()
        sep3.setProperty("cssClass", "separator")
        root.addWidget(sep3)

        btn_guide = QPushButton("📱  Hardware Key Guide")
        btn_guide.setObjectName("btn_key_guide")
        btn_guide.setToolTip("Physical Vol+/Vol-/Power combinations for Recovery, Fastboot & boot menus")
        btn_guide.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_guide.setStyleSheet("font-size: 11px; padding: 6px 10px; font-weight: 600;")
        btn_guide.clicked.connect(self.key_guide_requested.emit)
        root.addWidget(btn_guide)

        # Kept as programmatic children for backwards compatibility & unit tests
        self._btn_vol_up = QPushButton()
        self._btn_vol_up.setObjectName("btn_key_volup")
        self._btn_vol_up.setVisible(False)
        self._btn_vol_up.clicked.connect(lambda: self.key_event_requested.emit(24))
        root.addWidget(self._btn_vol_up)

        self._btn_vol_down = QPushButton()
        self._btn_vol_down.setObjectName("btn_key_voldown")
        self._btn_vol_down.setVisible(False)
        self._btn_vol_down.clicked.connect(lambda: self.key_event_requested.emit(25))
        root.addWidget(self._btn_vol_down)

        self._btn_power = QPushButton()
        self._btn_power.setObjectName("btn_key_power")
        self._btn_power.setVisible(False)
        self._btn_power.clicked.connect(lambda: self.key_event_requested.emit(26))
        root.addWidget(self._btn_power)

        root.addStretch()

    # ---- Internal Slots ---------------------------------------------------

    def _on_rescan_clicked(self) -> None:
        """Trigger device re-scan and restart ADB server if unauthorized."""
        if getattr(self, "_last_mode", "") == "unauthorized":
            self.restart_adb_requested.emit()
        else:
            self.refresh_requested.emit()

    # ---- Public API -------------------------------------------------------

    def set_mode(self, mode: str) -> None:
        """Update the mode indicator pill and helper guidance card."""
        self._last_mode = mode
        self._mode.set_mode(mode)

        if mode == "not_connected":
            self._helper_card.setVisible(True)
            self._helper_title.setText("💡 Phone Not Detected?")
            self._helper_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #C96E00;")
            self._helper_text.setText(
                "1. Settings > About Phone > Tap 'Build Number' 7x.\n"
                "2. Developer options > Turn ON 'USB Debugging'.\n"
                "3. Use a USB data cable (not charge-only)."
            )
            self._btn_rescan.setText("🔄 Scan")
        elif mode == "unauthorized":
            self._helper_card.setVisible(True)
            self._helper_title.setText("⚠️ USB Debugging Unauthorized")
            self._helper_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #FF9500;")
            self._helper_text.setText(
                "Unlock your phone screen now!\n"
                "Tap 'Always allow from this computer' on the RSA popup."
            )
            self._btn_rescan.setText("🔄 Resend")
        else:
            # Device connected in ready state
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
