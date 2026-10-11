"""
FlashDock — Device selector widget.

A dropdown + lock button that lets the user choose which device to
target when multiple phones are connected, and lock onto a serial
number for safety (Section 16 rule: device lock).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from flashdock.core.device import DeviceInfo
from flashdock.logger import get_logger

log = get_logger(__name__)


class DeviceSelector(QFrame):
    """Dropdown for picking the active device + a lock/unlock toggle.

    Signals
    -------
    device_selected(serial: str)
        Emitted when the user picks a different device.
    serial_locked(serial: str)
        Emitted when the user locks onto a serial.
    serial_unlocked()
        Emitted when the lock is removed.
    """

    device_selected = Signal(str)
    serial_locked = Signal(str)
    serial_unlocked = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(10)

        icon = QLabel("🔌")
        icon.setStyleSheet("font-size: 14px; background: transparent;")
        layout.addWidget(icon)

        self._combo = QComboBox()
        self._combo.setMinimumWidth(260)
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        layout.addWidget(self._combo, 1)

        self._lock_btn = QPushButton("🔒 Lock")
        self._lock_btn.setToolTip("Lock onto this device's serial number for safety")
        self._lock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lock_btn.setFixedWidth(90)
        self._lock_btn.clicked.connect(self._toggle_lock)
        layout.addWidget(self._lock_btn)

        self._locked_serial: Optional[str] = None
        self._devices: list[DeviceInfo] = []

    # ---- Public API -------------------------------------------------------

    def update_devices(self, devices: list[DeviceInfo], locked: Optional[str] = None) -> None:
        """Refresh the device dropdown.

        Parameters
        ----------
        devices : list[DeviceInfo]
            All detected devices.
        locked : str | None
            Currently locked serial (if any).
        """
        self._devices = devices
        self._locked_serial = locked

        self._combo.blockSignals(True)
        current_serial = self._current_serial()
        self._combo.clear()

        if not devices:
            self._combo.addItem("No device connected", "")
            self._lock_btn.setEnabled(False)
        else:
            for d in devices:
                label = f"{d.summary_line}  [{d.serial[:8]}…]" if len(d.serial) > 8 else f"{d.summary_line}  [{d.serial}]"
                self._combo.addItem(label, d.serial)
                # Re-select the previously selected device
                if d.serial == current_serial:
                    self._combo.setCurrentIndex(self._combo.count() - 1)
            self._lock_btn.setEnabled(True)

        self._update_lock_button()
        self._combo.blockSignals(False)

    def _current_serial(self) -> str:
        return self._combo.currentData() or ""

    # ---- Lock / Unlock -----------------------------------------------------

    def _toggle_lock(self) -> None:
        serial = self._current_serial()
        if self._locked_serial:
            self._locked_serial = None
            self._combo.setEnabled(True)
            self._update_lock_button()
            self.serial_unlocked.emit()
            log.info("Serial unlocked.")
        elif serial:
            self._locked_serial = serial
            self._combo.setEnabled(False)
            self._update_lock_button()
            self.serial_locked.emit(serial)
            log.info("Serial locked: %s", serial)

    def _update_lock_button(self) -> None:
        if self._locked_serial:
            self._lock_btn.setText("🔓 Unlock")
            self._lock_btn.setToolTip("Remove the serial lock")
            self._lock_btn.setStyleSheet("color: #FF9500; font-weight: 600; border-color: #FF9500;")
        else:
            self._lock_btn.setText("🔒 Lock")
            self._lock_btn.setToolTip("Lock onto this device's serial number for safety")
            self._lock_btn.setStyleSheet("")

    # ---- Combo change -------------------------------------------------------

    def _on_combo_changed(self, index: int) -> None:
        serial = self._combo.itemData(index) or ""
        if serial:
            self.device_selected.emit(serial)
            log.info("Device selected: %s", serial)
