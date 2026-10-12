"""
FlashDock — Universal Multi-Mode Reboot Switchboard (Section 2.1).

Adapted from Z3X, Chimera Tool, and Hydra Tool:
A prominent, unified switchboard for triggering instant hardware & software reboot modes:
- Reboot System (Normal Android OS)
- Reboot Bootloader / Fastboot
- Reboot FastbootD (Userspace dynamic partitions)
- Reboot Recovery (Stock / TWRP / OrangeFox)
- Reboot EDL 9008 (Qualcomm Sahara handshake)
- Reboot Download Mode (Samsung Odin)
- Power Off (Safe shutdown)
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flashdock.logger import get_logger
from flashdock.ui.icon_assets import create_icon_label, get_icon, get_icon_pixmap

log = get_logger(__name__)


class RebootSwitchboardDialog(QDialog):
    """
    Dedicated Power & Reboot Switchboard modal dialog (Z3X / Chimera style).
    Allows operators to reboot or power off the device with single-click precision.
    """

    reboot_mode_selected = Signal(str)

    _REBOOT_MODES = [
        ("system",     "Reboot System",      "Normal Android OS reboot",           "refresh",    "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #10B981, stop:1 #059669)"),
        ("bootloader", "Fastboot (BL)",       "Fastboot Bootloader mode",           "flash",      "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #007AFF, stop:1 #0056B3)"),
        ("fastbootd",  "FastbootD (Userspace)", "Fastboot userspace dynamic mode",   "flash",      "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00E5FF, stop:1 #0097A7)"),
        ("recovery",   "Recovery Mode",      "Stock, TWRP, or OrangeFox recovery", "tools",      "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #AF52DE, stop:1 #7E22CE)"),
        ("edl",        "Qualcomm EDL 9008",  "Emergency Download Sahara mode",     "usb",        "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EF4444, stop:1 #B91C1C)"),
        ("download",   "Samsung Odin Mode",  "Samsung Download Mode protocol",     "downloads",  "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00B4D8, stop:1 #0077B6)"),
        ("poweroff",   "Power Off",          "Immediate system shutdown",          "power",      "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #64748B, stop:1 #334155)"),
    ]

    def __init__(
        self,
        device_or_serial: DeviceInfo | str = "",
        current_mode: str = "system",
        parent: Optional[QWidget] = None,
        device: Optional[DeviceInfo] = None,
    ) -> None:
        super().__init__(parent)
        dev = device if device is not None else (device_or_serial if isinstance(device_or_serial, DeviceInfo) else None)
        serial = dev.serial if dev else (str(device_or_serial) if isinstance(device_or_serial, str) else "")
        current_mode = dev.mode if dev else current_mode

        self.setWindowTitle("Power & Reboot Switchboard — FlashDock")
        self.setFixedSize(540, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # Header
        header_row = QHBoxLayout()
        header_row.setSpacing(10)
        header_row.addWidget(create_icon_label("power", 24, color="#007AFF"))

        header_col = QVBoxLayout()
        header_col.setSpacing(2)
        title_lbl = QLabel("Power & Reboot Switchboard")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #E6EDF3;")
        desc_lbl = QLabel(f"Target: {serial or 'Connected Device'} (Current State: {current_mode.upper()})")
        desc_lbl.setStyleSheet("font-size: 11px; color: #8B949E;")
        header_col.addWidget(title_lbl)
        header_col.addWidget(desc_lbl)
        header_row.addLayout(header_col, 1)
        root.addLayout(header_row)

        # Grid of Reboot Options
        grid = QGridLayout()
        grid.setSpacing(10)

        for idx, (mode_id, title, desc, icon_name, grad) in enumerate(self._REBOOT_MODES):
            row = idx // 2
            col = idx % 2

            btn = QPushButton()
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(72)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #181E26;
                    border: 1px solid #2C3644;
                    border-radius: 12px;
                    text-align: left;
                    padding: 8px 12px;
                }
                QPushButton:hover {
                    background-color: #222C3D;
                    border-color: #0A84FF;
                }
                QPushButton:pressed {
                    background-color: #12171E;
                }
            """)
            btn_lay = QHBoxLayout(btn)
            btn_lay.setContentsMargins(8, 6, 8, 6)
            btn_lay.setSpacing(10)

            # Circular Badge Chip
            chip = QFrame()
            chip.setFixedSize(32, 32)
            chip.setStyleSheet(f"background: {grad}; border-radius: 16px; border: none;")
            chip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            chip_lay = QHBoxLayout(chip)
            chip_lay.setContentsMargins(0, 0, 0, 0)
            chip_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chip_ico = QLabel()
            chip_ico.setPixmap(get_icon_pixmap(icon_name, width=16, height=16, color="#FFFFFF"))
            chip_ico.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            chip_lay.addWidget(chip_ico)
            btn_lay.addWidget(chip)

            # Text Labels
            text_col = QVBoxLayout()
            text_col.setContentsMargins(0, 0, 0, 0)
            text_col.setSpacing(2)
            t_lbl = QLabel(title)
            t_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #E6EDF3; background: transparent;")
            t_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            d_lbl = QLabel(desc)
            d_lbl.setStyleSheet("font-size: 10px; color: #8B949E; background: transparent;")
            d_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            text_col.addWidget(t_lbl)
            text_col.addWidget(d_lbl)
            btn_lay.addLayout(text_col, 1)

            btn.clicked.connect(lambda checked=False, m=mode_id: self._on_select_mode(m))
            grid.addWidget(btn, row, col)

        root.addLayout(grid)
        root.addStretch(1)

        # Footer Cancel Button
        footer_row = QHBoxLayout()
        footer_row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.reject)
        footer_row.addWidget(close_btn)
        root.addLayout(footer_row)

    def _on_select_mode(self, mode_id: str) -> None:
        log.info("Switchboard selected reboot mode: %s", mode_id)
        self.reboot_mode_selected.emit(mode_id)
        self.accept()

    _on_mode_clicked = _on_select_mode

