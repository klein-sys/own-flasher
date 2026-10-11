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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(220)

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

        # ---- Separator ----
        sep = QFrame()
        sep.setProperty("cssClass", "separator")
        root.addWidget(sep)

        # ---- Reboot buttons ----
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

        # ---- Refresh button (always enabled) ----
        refresh_btn = QPushButton("🔄  Refresh connection")
        refresh_btn.setObjectName("refresh_btn")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        root.addWidget(refresh_btn)

        root.addStretch()

    # ---- Public API -------------------------------------------------------

    def set_mode(self, mode: str) -> None:
        """Update the mode indicator pill."""
        self._mode.set_mode(mode)

    def set_summary(self, text: str) -> None:
        """Update the short device summary text."""
        self._summary.setText(text)

    def enable_buttons(self, allowed: list[str]) -> None:
        """Enable only the buttons whose *mode_id* is in *allowed*."""
        for mode_id, btn in self._buttons.items():
            btn.setEnabled(mode_id in allowed)
            if mode_id not in allowed:
                btn.setToolTip(f"Not available in current mode")
