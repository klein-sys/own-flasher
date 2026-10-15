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
from flashdock.ui.icon_assets import create_icon_label, get_icon

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
    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._layout = layout

        icon = create_icon_label("search", 13, color="#0A84FF")
        layout.addWidget(icon)

        self._combo = QComboBox()
        self._combo.setMinimumWidth(200)
        self._combo.setMaximumWidth(280)
        self._combo.setFixedHeight(28)
        self._combo.addItem("No device connected", "")
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        layout.addWidget(self._combo)

        # Dedicated 1-click Refresh Devices button
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setIcon(get_icon("refresh", 13))
        self._refresh_btn.setToolTip("Scan USB buses and query connected ADB/Fastboot devices")
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.setFixedHeight(28)
        self._refresh_btn.setStyleSheet("""
            QPushButton {
                background: rgba(10, 132, 255, 0.12);
                color: #0A84FF;
                border: 1px solid rgba(10, 132, 255, 0.3);
                border-radius: 7px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(10, 132, 255, 0.22);
            }
        """)
        self._refresh_btn.clicked.connect(self.refresh_requested.emit)
        layout.addWidget(self._refresh_btn)

        # Safety Pin Serial Button
        self._lock_btn = QPushButton("Pin Serial")
        self._lock_btn.setIcon(get_icon("lock", 13))
        self._lock_btn.setToolTip("Pin onto this device's serial number so commands are never accidentally sent to another connected device.")
        self._lock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lock_btn.setFixedHeight(28)
        self._lock_btn.setMinimumWidth(85)
        self._lock_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 7px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 600;
                color: #E6EDF3;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.12);
            }
        """)
        self._lock_btn.clicked.connect(self._toggle_lock)
        layout.addWidget(self._lock_btn)

        self._locked_serial: Optional[str] = None
        self._devices: list[DeviceInfo] = []
        self.apply_theme("dark")

    def add_action_widget(self, widget: QWidget) -> None:
        """Add an action button or widget to the right side of the device controls."""
        self._layout.addWidget(widget)

    def apply_theme(self, theme: str = "dark") -> None:
        """Apply dark or light theme to the compact device selector."""
        if theme == "light":
            self.setStyleSheet("DeviceSelector { background: transparent; border: none; }")
            self._combo.setStyleSheet("""
                QComboBox {
                    background-color: #FFFFFF;
                    border: 1px solid #DCE1E8;
                    border-radius: 7px;
                    padding: 2px 10px;
                    color: #1C2024;
                    font-size: 11.5px;
                }
                QComboBox:hover {
                    border: 1px solid #007AFF;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox QAbstractItemView {
                    background-color: #FFFFFF;
                    border: 1px solid #DCE1E8;
                    selection-background-color: #007AFF;
                    color: #1C2024;
                }
            """)
            if not self._locked_serial:
                self._lock_btn.setStyleSheet("""
                    QPushButton {
                        background: #FFFFFF;
                        border: 1px solid #DCE1E8;
                        border-radius: 7px;
                        padding: 2px 10px;
                        font-size: 11px;
                        font-weight: 600;
                        color: #1C2024;
                    }
                    QPushButton:hover {
                        background: #EAEFF5;
                    }
                """)
        else:
            self.setStyleSheet("DeviceSelector { background: transparent; border: none; }")
            self._combo.setStyleSheet("""
                QComboBox {
                    background-color: rgba(255, 255, 255, 0.06);
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 7px;
                    padding: 2px 10px;
                    color: #E6EDF3;
                    font-size: 11.5px;
                }
                QComboBox:hover {
                    border: 1px solid rgba(10, 132, 255, 0.5);
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox QAbstractItemView {
                    background-color: #161B22;
                    border: 1px solid rgba(255, 255, 255, 0.15);
                    selection-background-color: #0A84FF;
                    color: #E6EDF3;
                }
            """)
            if not self._locked_serial:
                self._lock_btn.setStyleSheet("""
                    QPushButton {
                        background: rgba(255, 255, 255, 0.06);
                        border: 1px solid rgba(255, 255, 255, 0.12);
                        border-radius: 7px;
                        padding: 2px 10px;
                        font-size: 11px;
                        font-weight: 600;
                        color: #E6EDF3;
                    }
                    QPushButton:hover {
                        background: rgba(255, 255, 255, 0.12);
                    }
                """)

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
            self._lock_btn.setText("Unpin Serial")
            self._lock_btn.setIcon(get_icon("unlock", 13, color="#FF9F0A"))
            self._lock_btn.setToolTip("Unpin from this serial number")
            self._lock_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 149, 0, 0.16);
                    color: #FF9F0A;
                    border: 1px solid #FF9F0A;
                    border-radius: 7px;
                    padding: 2px 10px;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background: rgba(255, 149, 0, 0.26);
                }
            """)
        else:
            self._lock_btn.setText("Pin Serial")
            self._lock_btn.setIcon(get_icon("lock", 13))
            self._lock_btn.setToolTip("Pin onto this device's serial number so commands are never accidentally sent to another connected device.")
            self._lock_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.06);
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 7px;
                    padding: 2px 10px;
                    font-size: 11px;
                    font-weight: 600;
                    color: #E6EDF3;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.12);
                }
            """)

    # ---- Combo change -------------------------------------------------------

    def _on_combo_changed(self, index: int) -> None:
        serial = self._combo.itemData(index) or ""
        if serial:
            self.device_selected.emit(serial)
            log.info("Device selected: %s", serial)
