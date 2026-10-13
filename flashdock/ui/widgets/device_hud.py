"""
FlashDock — Live Device State Visualizer & Diagnostics HUD (Section 1).

Inspired by professional GSM repair suites (Chimera Tool, Pandora Tool, UnlockTool):
- Elevated visualizer banner with Live Connection Mode Pill (Emerald ADB, Cobalt Fastboot,
  Crimson EDL 9008, Orange MTK BROM, Cyan Odin, Purple Recovery).
- Real-time telemetry gauges: Battery %, temperature & voltage, SoC / Chipset model,
  Bootloader lock status, Active slot (_a / _b), Knox warranty bit (0x0 / 0x1),
  and Security patch level.
- Live Operation Progress & Stepped Pipeline HUD tracker:
  ([1/4] Handshake OK -> [2/4] Partition Table -> [3/4] Write Flash -> [4/4] SHA-256 Verified).
- Auto-Rescue 1-Click Fallback trigger: Restores emergency pre-flash blocks on failed writes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from flashdock.constants import DATA_DIR
from flashdock.core.device import DeviceInfo
from flashdock.logger import get_logger
from flashdock.ui.icon_assets import get_icon, get_icon_pixmap

log = get_logger(__name__)


class LiveDeviceHud(QFrame):
    """
    Elevated real-time device diagnostics HUD and stepped pipeline tracker.
    Positioned prominently above the tool workspace.
    """

    restore_preflash_requested = Signal(str)  # Emits device serial

    _MODE_CONFIGS = {
        "system":       ("ADB Authorized", "#34C759", "phone"),
        "recovery":     ("Recovery Mode", "#AF52DE", "tools"),
        "bootloader":   ("Fastboot (BL)", "#007AFF", "flash"),
        "fastbootd":    ("FastbootD (Userspace)", "#00E5FF", "flash"),
        "download":     ("Samsung Odin Mode", "#00B4D8", "downloads"),
        "edl":          ("Qualcomm EDL 9008", "#FF3B30", "usb"),
        "brom":         ("MediaTek BROM", "#FF9500", "mtk_unisoc"),
        "sideload":     ("ADB Sideload", "#FF9500", "refresh"),
        "unauthorized": ("Unauthorized (RSA)", "#FF9500", "warning"),
        "offline":      ("Device Offline", "#8E8E93", "info"),
        "not_connected":("No Device Connected", "#8E8E93", "info"),
    }

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("liveDeviceHud")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(82)

        self._current_device: Optional[DeviceInfo] = None
        self._current_theme = "dark"
        self._is_operation_active = False

        # Main Layout
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(14, 6, 14, 6)
        root_lay.setSpacing(6)

        # Top Row: Mode Capsule + Telemetry Metrics
        self._top_row = QHBoxLayout()
        self._top_row.setSpacing(12)

        # 1. Live Connection Mode Pill
        self._mode_pill = QFrame()
        self._mode_pill.setFixedHeight(28)
        pill_lay = QHBoxLayout(self._mode_pill)
        pill_lay.setContentsMargins(8, 2, 10, 2)
        pill_lay.setSpacing(6)

        self._mode_dot = QLabel("●")
        self._mode_dot.setStyleSheet("font-size: 11px;")
        self._mode_text = QLabel("No Device Connected")
        self._mode_text.setStyleSheet("font-size: 11px; font-weight: 700; letter-spacing: 0.3px;")
        pill_lay.addWidget(self._mode_dot)
        pill_lay.addWidget(self._mode_text)
        self._top_row.addWidget(self._mode_pill)

        # 2. Telemetry Gauges (Battery, Chipset, BL, Slot, Knox, Patch)
        self._gauge_container = QHBoxLayout()
        self._gauge_container.setSpacing(14)

        # Battery Gauge
        self._gauge_batt = QLabel("Batt: —")
        self._gauge_batt.setStyleSheet("font-size: 11px; font-weight: 600;")
        self._gauge_container.addWidget(self._gauge_batt)

        # Chipset / SoC
        self._gauge_soc = QLabel("SoC: —")
        self._gauge_soc.setStyleSheet("font-size: 11px; font-weight: 600;")
        self._gauge_container.addWidget(self._gauge_soc)

        # Bootloader Lock State
        self._gauge_bl = QLabel("BL: —")
        self._gauge_bl.setStyleSheet("font-size: 11px; font-weight: 700;")
        self._gauge_container.addWidget(self._gauge_bl)

        # Active Slot
        self._gauge_slot = QLabel("Slot: —")
        self._gauge_slot.setStyleSheet("font-size: 11px; font-weight: 600;")
        self._gauge_container.addWidget(self._gauge_slot)

        # Knox Warranty Bit
        self._gauge_knox = QLabel("Knox: —")
        self._gauge_knox.setStyleSheet("font-size: 11px; font-weight: 600;")
        self._gauge_container.addWidget(self._gauge_knox)

        # Security Patch Level
        self._gauge_patch = QLabel("Patch: —")
        self._gauge_patch.setStyleSheet("font-size: 11px; font-weight: 500;")
        self._gauge_container.addWidget(self._gauge_patch)

        # Root State Pill
        self._gauge_root = QLabel("ROOT: —")
        self._gauge_root.setStyleSheet("font-size: 11px; font-weight: 700; color: #8E8E93;")
        self._gauge_container.addWidget(self._gauge_root)

        # ROM State Pill
        self._gauge_rom = QLabel("ROM: —")
        self._gauge_rom.setStyleSheet("font-size: 11px; font-weight: 700; color: #8E8E93;")
        self._gauge_container.addWidget(self._gauge_rom)

        self._top_row.addLayout(self._gauge_container)
        self._top_row.addStretch(1)

        # Emergency Pre-Flash Auto-Rescue Button (hidden until failure or emergency backup exists)
        self._btn_rescue = QPushButton("Restore Pre-Flash State")
        self._btn_rescue.setIcon(get_icon("unbrick", 13, color="#FFFFFF"))
        self._btn_rescue.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_rescue.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #EF4444, stop:1 #B91C1C);
                color: #FFFFFF;
                font-weight: 700;
                font-size: 11px;
                padding: 4px 10px;
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #DC2626, stop:1 #991B1B);
            }
        """)
        self._btn_rescue.setToolTip("1-click restore of critical partitions (boot, init_boot, vbmeta, persist, efs) saved before flashing")
        self._btn_rescue.clicked.connect(self._on_restore_clicked)
        self._btn_rescue.setVisible(False)
        self._top_row.addWidget(self._btn_rescue)

        root_lay.addLayout(self._top_row)

        # Bottom Row: Stepped Pipeline Tracker & Operation Progress
        self._bottom_row = QHBoxLayout()
        self._bottom_row.setSpacing(8)

        self._step_labels: list[QLabel] = []
        step_names = [
            "[1/4] Handshake OK",
            "[2/4] Partition Table",
            "[3/4] Flashing Data",
            "[4/4] SHA-256 Verified",
        ]
        for name in step_names:
            lbl = QLabel(name)
            lbl.setStyleSheet("font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; background: rgba(0,0,0,0.15); color: #8E8E93;")
            self._step_labels.append(lbl)
            self._bottom_row.addWidget(lbl)

        # Progress bar
        self._prog_bar = QProgressBar()
        self._prog_bar.setFixedHeight(6)
        self._prog_bar.setTextVisible(False)
        self._prog_bar.setValue(0)
        self._prog_bar.setStyleSheet("""
            QProgressBar {
                background: rgba(0,0,0,0.2);
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007AFF, stop:1 #00F2FE);
                border-radius: 3px;
            }
        """)
        self._bottom_row.addWidget(self._prog_bar, 1)

        self._stage_status_text = QLabel("Standby")
        self._stage_status_text.setStyleSheet("font-size: 10px; color: #8E8E93; font-weight: 500;")
        self._bottom_row.addWidget(self._stage_status_text)

        root_lay.addLayout(self._bottom_row)

        self.apply_theme("dark")

    # -----------------------------------------------------------------------
    # Public Update Handlers
    # -----------------------------------------------------------------------

    def update_device(self, info: Optional[DeviceInfo]) -> None:
        """Update live connection mode, telemetry gauges and rescue state."""
        self._current_device = info
        if not info or info.mode in ("not_connected", "offline", ""):
            self._set_mode_ui("not_connected")
            self._gauge_batt.setText("Batt: —")
            self._gauge_soc.setText("SoC: —")
            self._gauge_bl.setText("BL: —")
            self._gauge_slot.setText("Slot: —")
            self._gauge_knox.setText("Knox: —")
            self._gauge_patch.setText("Patch: —")
            self._gauge_root.setText("ROOT: —")
            self._gauge_root.setStyleSheet("font-size: 11px; font-weight: 700; color: #8E8E93;")
            self._gauge_rom.setText("ROM: —")
            self._gauge_rom.setStyleSheet("font-size: 11px; font-weight: 700; color: #8E8E93;")
            self._btn_rescue.setVisible(False)
            return

        # 1. Update Connection Mode
        self._set_mode_ui(info.mode)

        # 2. Battery Telemetry
        if info.battery_level >= 0:
            batt_text = f"Batt: {info.battery_level}%"
            if info.battery_temp_c > 0:
                batt_text += f" ({info.battery_temp_c}°C)"
            if info.battery_voltage_mv > 0:
                batt_text += f" {info.battery_voltage_mv}mV"
            color = "#34C759" if info.battery_level >= 30 else "#EF4444"
            self._gauge_batt.setText(batt_text)
            self._gauge_batt.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {color};")
        else:
            self._gauge_batt.setText("Batt: Unknown")
            self._gauge_batt.setStyleSheet("font-size: 11px; font-weight: 600; color: #8E8E93;")

        # 3. Chipset / SoC
        soc_display = info.chipset_family.title() if info.chipset_family != "unknown" else (info.hardware or info.chipset)
        if soc_display and soc_display != "unknown":
            self._gauge_soc.setText(f"SoC: {soc_display}")
            self._gauge_soc.setStyleSheet("font-size: 11px; font-weight: 600; color: #007AFF;")
        else:
            self._gauge_soc.setText("SoC: Unknown")
            self._gauge_soc.setStyleSheet("font-size: 11px; font-weight: 600; color: #8E8E93;")

        # 4. Bootloader Lock State
        if info.bootloader_state == "unlocked":
            self._gauge_bl.setText("BL: UNLOCKED")
            self._gauge_bl.setStyleSheet("font-size: 11px; font-weight: 700; color: #34C759;")
        elif info.bootloader_state == "locked":
            self._gauge_bl.setText("BL: LOCKED")
            self._gauge_bl.setStyleSheet("font-size: 11px; font-weight: 700; color: #EF4444;")
        else:
            self._gauge_bl.setText("BL: Unknown")
            self._gauge_bl.setStyleSheet("font-size: 11px; font-weight: 700; color: #8E8E93;")

        # 5. Active Slot
        if info.slot_scheme == "a/b":
            active = f"_{info.active_slot}" if info.active_slot else "A/B"
            self._gauge_slot.setText(f"Slot: {active}")
            self._gauge_slot.setStyleSheet("font-size: 11px; font-weight: 600; color: #AF52DE;")
        elif info.slot_scheme == "a_only":
            self._gauge_slot.setText("Slot: A-only")
            self._gauge_slot.setStyleSheet("font-size: 11px; font-weight: 600; color: #8E8E93;")
        else:
            self._gauge_slot.setText("Slot: —")
            self._gauge_slot.setStyleSheet("font-size: 11px; font-weight: 600; color: #8E8E93;")

        # 6. Knox Warranty Bit
        if info.knox_warranty_bit == "0x1":
            self._gauge_knox.setText("Knox: 0x1 (Tripped)")
            self._gauge_knox.setStyleSheet("font-size: 11px; font-weight: 600; color: #EF4444;")
        elif info.knox_warranty_bit == "0x0" and info.brand.lower() == "samsung":
            self._gauge_knox.setText("Knox: 0x0 (Clean)")
            self._gauge_knox.setStyleSheet("font-size: 11px; font-weight: 600; color: #34C759;")
        else:
            self._gauge_knox.setText("Knox: 0x0")
            self._gauge_knox.setStyleSheet("font-size: 11px; font-weight: 600; color: #8E8E93;")

        # 7. Security Patch
        patch = info.security_patch or "—"
        self._gauge_patch.setText(f"Patch: {patch}")

        # 8. Root State Pill
        if info.is_rooted:
            method_str = f" ({info.root_method.title()})" if info.root_method else ""
            self._gauge_root.setText(f"ROOT: YES{method_str}")
            self._gauge_root.setStyleSheet("font-size: 11px; font-weight: 700; color: #34C759; background: rgba(52, 199, 89, 0.15); border: 1px solid rgba(52, 199, 89, 0.3); border-radius: 4px; padding: 1px 6px;")
        elif info.mode in ("system", "recovery"):
            self._gauge_root.setText("ROOT: NO")
            self._gauge_root.setStyleSheet("font-size: 11px; font-weight: 600; color: #8E8E93; background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 4px; padding: 1px 6px;")
        else:
            self._gauge_root.setText("ROOT: —")
            self._gauge_root.setStyleSheet("font-size: 11px; font-weight: 600; color: #8E8E93;")

        # 9. ROM / Firmware Type Indicator Pill
        is_gsi = info.os_type == "gsi" or "treble" in info.build_display.lower() or "gsi" in info.build_fingerprint.lower()
        is_custom = info.os_type == "custom_rom" or "test-keys" in info.build_fingerprint.lower() or "lineage" in info.build_display.lower() or "pixelos" in info.build_display.lower()
        is_stock = info.os_type == "stock" or (info.build_fingerprint and "release-keys" in info.build_fingerprint.lower() and not is_gsi and not is_custom)

        if is_gsi:
            self._gauge_rom.setText("ROM: CUSTOM GSI")
            self._gauge_rom.setStyleSheet("font-size: 11px; font-weight: 700; color: #AF52DE; background: rgba(175, 82, 222, 0.15); border: 1px solid rgba(175, 82, 222, 0.3); border-radius: 4px; padding: 1px 6px;")
        elif is_custom:
            self._gauge_rom.setText("ROM: CUSTOM ROM")
            self._gauge_rom.setStyleSheet("font-size: 11px; font-weight: 700; color: #FF9F0A; background: rgba(255, 159, 10, 0.15); border: 1px solid rgba(255, 159, 10, 0.3); border-radius: 4px; padding: 1px 6px;")
        elif is_stock:
            self._gauge_rom.setText("ROM: OFFICIAL STOCK")
            self._gauge_rom.setStyleSheet("font-size: 11px; font-weight: 700; color: #007AFF; background: rgba(0, 122, 255, 0.15); border: 1px solid rgba(0, 122, 255, 0.3); border-radius: 4px; padding: 1px 6px;")
        elif info.mode in ("system", "recovery"):
            self._gauge_rom.setText(f"ROM: {info.os_display.upper()}")
            self._gauge_rom.setStyleSheet("font-size: 11px; font-weight: 600; color: #007AFF; background: rgba(0, 122, 255, 0.1); border-radius: 4px; padding: 1px 6px;")
        else:
            self._gauge_rom.setText("ROM: —")
            self._gauge_rom.setStyleSheet("font-size: 11px; font-weight: 600; color: #8E8E93;")

        # 10. Check if emergency pre-flash backup exists for this device
        self._check_emergency_backup_available(info.serial)

    def set_stepped_stage(self, stage_idx: int, stage_desc: str, pct: int = 0) -> None:
        """
        Update stepped operation pipeline HUD:
        stage_idx: 1, 2, 3, or 4
        """
        self._is_operation_active = True
        self._stage_status_text.setText(stage_desc)
        self._prog_bar.setValue(max(0, min(100, pct)))

        for i, lbl in enumerate(self._step_labels, start=1):
            if i < stage_idx:
                # Completed
                lbl.setStyleSheet("font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; background: rgba(52, 199, 89, 0.2); color: #34C759;")
            elif i == stage_idx:
                # Active
                lbl.setStyleSheet("font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px; background: rgba(0, 122, 255, 0.3); color: #007AFF; border: 1px solid #007AFF;")
            else:
                # Pending
                lbl.setStyleSheet("font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; background: rgba(0,0,0,0.15); color: #8E8E93;")

    def reset_pipeline(self, final_msg: str = "Standby") -> None:
        """Reset stepped pipeline to idle."""
        self._is_operation_active = False
        self._stage_status_text.setText(final_msg)
        self._prog_bar.setValue(0)
        for lbl in self._step_labels:
            lbl.setStyleSheet("font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; background: rgba(0,0,0,0.15); color: #8E8E93;")

    def trigger_failure_alert(self, err_msg: str) -> None:
        """Indicate operation failure and present emergency restore option."""
        self._stage_status_text.setText(f"Operation Aborted: {err_msg[:45]}")
        self._stage_status_text.setStyleSheet("font-size: 10px; color: #EF4444; font-weight: 700;")
        self._prog_bar.setStyleSheet("""
            QProgressBar { background: rgba(239, 68, 68, 0.2); border-radius: 3px; }
            QProgressBar::chunk { background: #EF4444; border-radius: 3px; }
        """)
        if self._current_device and self._current_device.serial:
            self._btn_rescue.setVisible(True)

    def apply_theme(self, theme: str) -> None:
        """Apply dark/light styling."""
        self._current_theme = theme.lower()
        if self._current_theme == "light":
            self.setStyleSheet("""
                QFrame#liveDeviceHud {
                    background-color: #F8F9FA;
                    border: 1px solid #DCE1E8;
                    border-radius: 12px;
                }
            """)
            self._gauge_patch.setStyleSheet("font-size: 11px; font-weight: 500; color: #5A6572;")
        else:
            self.setStyleSheet("""
                QFrame#liveDeviceHud {
                    background-color: #141820;
                    border: 1px solid #252D38;
                    border-radius: 12px;
                }
            """)
            self._gauge_patch.setStyleSheet("font-size: 11px; font-weight: 500; color: #8B949E;")

        if self._current_device:
            self.update_device(self._current_device)

    # -----------------------------------------------------------------------
    # Internal Helpers
    # -----------------------------------------------------------------------

    def _set_mode_ui(self, mode: str) -> None:
        label, color, icon_name = self._MODE_CONFIGS.get(mode, (mode.title(), "#8E8E93", "info"))
        self._mode_dot.setStyleSheet(f"color: {color}; font-size: 11px;")
        self._mode_text.setText(label)
        self._mode_text.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 700; letter-spacing: 0.3px;")
        self._mode_pill.setStyleSheet(f"""
            background: rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.15);
            border: 1px solid {color};
            border-radius: 14px;
        """)

    def _check_emergency_backup_available(self, serial: str) -> None:
        if not serial:
            self._btn_rescue.setVisible(False)
            return
        emergency_dir = DATA_DIR / "backups" / "emergency_preflash" / serial
        has_backup = emergency_dir.exists() and any(emergency_dir.glob("*.img"))
        self._btn_rescue.setVisible(has_backup)

    def _on_restore_clicked(self) -> None:
        if self._current_device and self._current_device.serial:
            log.info("Emergency Pre-Flash Restore requested for %s", self._current_device.serial)
            self.restore_preflash_requested.emit(self._current_device.serial)
