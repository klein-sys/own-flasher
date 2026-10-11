"""
FlashDock — Device summary card widget.

Shows a detailed card with all detected device information, organised
into sections.  This is what users see when they click "Check my phone"
or when a device is first connected.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from flashdock.core.device import DeviceInfo
from flashdock.logger import get_logger
from flashdock.ui.brand_assets import get_brand_pixmap

log = get_logger(__name__)


class _InfoRow(QFrame):
    """A single key → value row in the summary card."""

    def __init__(self, key: str, value: str, status: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        key_label = QLabel(key)
        key_label.setProperty("cssClass", "secondary")
        key_label.setFixedWidth(160)
        layout.addWidget(key_label)

        val_label = QLabel(value or "—")
        val_label.setStyleSheet("font-family: 'JetBrains Mono', 'Cascadia Code', monospace; font-size: 12px; font-weight: 500;")
        val_label.setWordWrap(True)
        layout.addWidget(val_label, 1)

        if status:
            status_colors = {
                "ok": "#22c55e",
                "warning": "#eab308",
                "error": "#ef4444",
                "info": "#3b82f6",
                "unknown": "#86868b",
            }
            color = status_colors.get(status, "#86868b")
            status_label = QLabel("●")
            status_label.setStyleSheet(f"color: {color}; font-size: 9px;")
            layout.addWidget(status_label)

        self._val_label = val_label

    def update_value(self, value: str, status: str = "") -> None:
        self._val_label.setText(value or "—")


class _Section(QGroupBox):
    """A titled section with key-value rows."""

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(title, parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 4, 8, 4)
        self._layout.setSpacing(0)

    def add_row(self, key: str, value: str, status: str = "") -> _InfoRow:
        row = _InfoRow(key, value, status)
        self._layout.addWidget(row)
        return row


class DeviceCard(QScrollArea):
    """Scrollable device info card populated from a :class:`DeviceInfo`."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self.setWidget(self._container)

        # Placeholder
        self._empty_label = QLabel("Connect a phone via USB and click\n\"Check my phone\" to see device details.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setProperty("cssClass", "secondary")
        self._empty_label.setStyleSheet("font-size: 13px; padding: 60px;")
        self._layout.addWidget(self._empty_label)
        self._layout.addStretch()

    def update_device(self, info: Optional[DeviceInfo]) -> None:
        """Rebuild the card contents from a DeviceInfo snapshot."""
        # Clear existing widgets
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not info or info.mode == "not_connected":
            self._empty_label = QLabel("No device connected.\nPlug in your phone with a USB cable.")
            self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._empty_label.setProperty("cssClass", "secondary")
            self._empty_label.setStyleSheet("font-size: 13px; padding: 60px;")
            self._layout.addWidget(self._empty_label)
            self._layout.addStretch()
            return

        # ---- Header with Brand Vector Logo ----
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        logo_lbl = QLabel()
        logo_lbl.setPixmap(get_brand_pixmap(info.brand, width=64, height=28))
        header_row.addWidget(logo_lbl)

        header_text = QLabel(info.summary_line)
        header_text.setProperty("cssClass", "heading")
        header_row.addWidget(header_text, 1)
        self._layout.addLayout(header_row)

        # ---- Detection warnings ----
        for err in info.detection_errors:
            warn = QLabel(f"⚠️  {err}")
            warn.setWordWrap(True)
            warn.setProperty("cssClass", "warn_banner")
            self._layout.addWidget(warn)

        # ---- Identity section ----
        identity = _Section("Identity")
        identity.add_row("Brand", info.brand.title() if info.brand else "—")
        identity.add_row("Model", info.model)
        identity.add_row("Codename", info.device)
        identity.add_row("Product", info.product)
        identity.add_row("Serial", info.serial)
        self._layout.addWidget(identity)

        # ---- Software section ----
        sw = _Section("Software")
        sw.add_row("OS Classification", info.os_display, status="ok" if info.os_type == "stock" else "warning" if info.os_type == "gsi" else "info")
        sw.add_row("Android", info.android_version)
        sw.add_row("SDK", info.sdk_version)
        sw.add_row("Security Patch", info.security_patch)
        sw.add_row("Build Number", info.build_number)
        sw.add_row("Build Fingerprint", info.build_fingerprint)
        sw.add_row("Kernel", info.kernel_version)
        self._layout.addWidget(sw)

        # ---- Hardware section ----
        hw = _Section("Hardware")
        hw.add_row("Chipset", info.chipset.title() if info.chipset != "unknown" else "Unknown")
        hw.add_row("CPU ABI", info.cpu_abi)
        hw.add_row("Hardware", info.hardware)
        hw.add_row("Board", info.board)
        self._layout.addWidget(hw)

        # ---- Bootloader & Partitions ----
        bl = _Section("Bootloader & Partitions")
        bl_status = "ok" if info.bootloader_state == "unlocked" else (
            "error" if info.bootloader_state == "locked" else "unknown"
        )
        bl.add_row("Bootloader", info.bootloader_state.title(), status=bl_status)

        oem_status = "ok" if info.oem_unlock_allowed == "1" else (
            "error" if info.oem_unlock_allowed == "0" else "unknown"
        )
        oem_text = {"1": "Allowed", "0": "Not allowed"}.get(info.oem_unlock_allowed, "Unknown")
        bl.add_row("OEM Unlock", oem_text, status=oem_status)

        bl.add_row("Slot Scheme", info.slot_scheme.upper())
        if info.active_slot:
            bl.add_row("Active Slot", info.active_slot.upper())
        bl.add_row("Dynamic Partitions", "Yes" if info.has_dynamic_partitions else "No")
        bl.add_row("Treble", "Yes" if info.treble_enabled else "No")
        if info.anti_rollback_index:
            bl.add_row("Anti-Rollback", info.anti_rollback_index, status="warning")
        self._layout.addWidget(bl)

        # ---- Status section ----
        status = _Section("Status")
        if info.battery_level >= 0:
            batt_status = "ok" if info.battery_level >= 60 else "warning" if info.battery_level >= 30 else "error"
            status.add_row("Battery", f"{info.battery_level}%", status=batt_status)
        else:
            status.add_row("Battery", "Unknown")
        root_status = "ok" if info.is_rooted else "info"
        root_text = f"Yes ({info.root_method.title()})" if info.is_rooted else "No"
        status.add_row("Root", root_text, status=root_status)
        status.add_row("Encryption", info.encryption_state.title())
        status.add_row("Current Mode", info.mode.title())
        self._layout.addWidget(status)

        self._layout.addStretch()
        log.info("Device card updated for %s", info.summary_line)
